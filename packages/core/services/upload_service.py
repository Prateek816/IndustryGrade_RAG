
import os
import re
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from packages.core.models import Document, UploadSession
from packages.storage.s3_client import S3Client
from sqlalchemy import select
from packages.core.models import Document, UploadSession

class UploadValidationError(Exception):
    """Raised when upload request metadata is invalid."""


@dataclass
class UploadInitiation:
    document_id: uuid.UUID
    upload_session_id: uuid.UUID
    upload_url: str
    storage_key: str
    method: str
    required_headers: dict[str, str]
    expires_in: int


class UploadService:

    ALLOWED_CONTENT_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "text/markdown",
        "text/html",
    }

    def __init__(
        self,
        db: Session,
        storage: S3Client | None = None,
    ):
        self.db = db
        self.storage = storage or S3Client()

        self.max_upload_size = (
            int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024
        )

        self.url_expiry = int(
            os.getenv("PRESIGNED_URL_EXPIRY", "900")
        )

    @staticmethod
    def _validate_filename(filename: str) -> str:
        if not filename or not filename.strip():
            raise UploadValidationError("Filename is required")

        # Normalize Windows and Unix path separators.
        filename = filename.replace("\\", "/")
        filename = PurePosixPath(filename).name.strip()

        if not filename or filename in {".", ".."}:
            raise UploadValidationError("Invalid filename")

        if len(filename) > 255:
            raise UploadValidationError("Filename is too long")

        if "\x00" in filename:
            raise UploadValidationError("Invalid filename")

        return filename

    def _validate_request(
        self,
        filename: str,
        content_type: str,
        expected_size: int | None,
    ) -> str:

        filename = self._validate_filename(filename)

        content_type = content_type.strip().lower()

        if content_type not in self.ALLOWED_CONTENT_TYPES:
            raise UploadValidationError(
                f"Unsupported content type: {content_type}"
            )

        if expected_size is not None:
            if expected_size <= 0:
                raise UploadValidationError(
                    "File size must be greater than zero"
                )

            if expected_size > self.max_upload_size:
                raise UploadValidationError(
                    f"File exceeds maximum size of "
                    f"{self.max_upload_size // (1024 * 1024)} MB"
                )

        return filename

    def initiate_upload(
        self,
        *,
        filename: str,
        content_type: str,
        owner_id: str,
        title: str | None = None,
        source: str = "upload",
        expected_size: int | None = None,
    ) -> UploadInitiation:

        filename = self._validate_request(
            filename,
            content_type,
            expected_size,
        )

        document_id = uuid.uuid4()
        upload_session_id = uuid.uuid4()

        # Never use a client-provided filename as the object key.
        storage_key = (
            f"raw/{document_id}/{upload_session_id}/original"
        )

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self.url_expiry
        )

        with self.db.begin():

            document = Document(
                id=document_id,
                filename=filename,
                title=title or filename,
                source=source,
                owner_id=owner_id,
            )

            self.db.add(document)
            self.db.flush()

            upload_session = UploadSession(
                id=upload_session_id,
                document_id=document_id,
                storage_key=storage_key,
                filename=filename,
                expected_content_type=content_type,
                expected_size=expected_size,
                status="pending",
                expires_at=expires_at,
            )

            self.db.add(upload_session)
            self.db.flush()

            upload_url = self.storage.generate_presigned_upload_url(
                storage_key=storage_key,
                content_type=content_type,
                expiry=self.url_expiry,
            )

        return UploadInitiation(
            document_id=document_id,
            upload_session_id=upload_session_id,
            upload_url=upload_url,
            storage_key=storage_key,
            method="PUT",
            required_headers={
                "Content-Type": content_type,
            },
            expires_in=self.url_expiry,
        )

    def complete_upload(
    self,
    *,
    document_id: uuid.UUID,
    upload_session_id: uuid.UUID,
    owner_id: str,
    ) -> dict:

        result = {}

        with self.db.begin():

            upload_session = self.db.scalar(
                select(UploadSession)
                .where(
                    UploadSession.id == upload_session_id,
                    UploadSession.document_id == document_id,
                )
                .with_for_update()
            )

            if upload_session is None:
                raise UploadValidationError("Upload session not found")

            document = self.db.get(Document, document_id)

            if document is None or document.owner_id != owner_id:
                raise UploadValidationError("Document not found")

            # Completion can safely be retried.
            if upload_session.status != "pending":
                return {
                    "status": upload_session.status,
                    "upload_session_id": upload_session.id,
                }

            now = datetime.now(timezone.utc)

            if upload_session.expires_at <= now:
                upload_session.status = "expired"

                result = {
                    "status": "expired",
                    "upload_session_id": upload_session.id,
                }

            else:
                # Check that the object actually exists in RustFS.
                metadata = self.storage.head_object(
                    upload_session.storage_key
                )

                actual_size = metadata["ContentLength"]

                if actual_size <= 0:
                    upload_session.status = "rejected"
                    result = {
                        "status": "rejected",
                        "reason": "Uploaded file is empty",
                    }

                elif actual_size > self.max_upload_size:
                    upload_session.status = "rejected"
                    result = {
                        "status": "rejected",
                        "reason": "Uploaded file exceeds maximum size",
                    }

                elif (
                    upload_session.expected_size is not None
                    and actual_size != upload_session.expected_size
                ):
                    upload_session.status = "rejected"
                    result = {
                        "status": "rejected",
                        "reason": "Uploaded size does not match declared size",
                    }

                else:
                    upload_session.status = "uploaded"
                    upload_session.uploaded_at = now

                    result = {
                        "status": "uploaded",
                        "upload_session_id": upload_session.id,
                        "document_id": document_id,
                        "actual_size": actual_size,
                    }

        return result