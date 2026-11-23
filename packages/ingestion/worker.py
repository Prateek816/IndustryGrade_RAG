
import logging
import uuid

from sqlalchemy import select

from packages.core.database import SessionLocal
from packages.core.models import UploadSession
from packages.core.services.ingestion_service import IngestionService
from packages.ingestion.validation import (
    FileValidationError,
    validate_uploaded_object,

)
from packages.storage.s3_client import S3Client

import json

from packages.ingestion.parsing.docling_parser import (
    parse_rustfs_object,
)
from packages.ingestion.parsing.preprocess import (
    preprocess_document,
)

logger = logging.getLogger(__name__)


def process_upload_session(upload_session_id: uuid.UUID):
    """
    Validate an uploaded RustFS object and register its document version.

    Safe to retry:
    - Only claims sessions in 'uploaded' state.
    - IngestionService handles duplicate SHA-256 hashes.
    """

    # 1. Claim the upload session.
    with SessionLocal() as db:
        with db.begin():
            upload = db.scalar(
                select(UploadSession)
                .where(UploadSession.id == upload_session_id)
                .with_for_update()
            )

            if upload is None:
                logger.error("Upload session %s not found", upload_session_id)
                return

            if upload.status != "uploaded":
                logger.info(
                    "Skipping session %s with status %s",
                    upload_session_id,
                    upload.status,
                )
                return

            upload.status = "processing"

            # Copy values before closing the session.
            document_id = upload.document_id
            storage_key = upload.storage_key
            expected_content_type = upload.expected_content_type
            expected_size = upload.expected_size

    # 2. Validate the actual object and calculate SHA-256.
    try:
        storage = S3Client()

        validated = validate_uploaded_object(
            storage,
            storage_key=storage_key,
            expected_content_type=expected_content_type,
            expected_size=expected_size,
        )

    except FileValidationError as exc:
        with SessionLocal() as db:
            with db.begin():
                upload = db.get(UploadSession, upload_session_id)
                if upload:
                    upload.status = "rejected"

        logger.warning(
            "Upload %s rejected: %s",
            upload_session_id,
            exc,
        )
        return

    except Exception:
        # Infrastructure/transient errors should be retryable.
        with SessionLocal() as db:
            with db.begin():
                upload = db.get(UploadSession, upload_session_id)
                if upload and upload.status == "processing":
                    upload.status = "uploaded"

        logger.exception(
            "Unexpected validation error for %s",
            upload_session_id,
        )
        raise

    # 3. Register the version and create its ingestion job.
    try:
        with SessionLocal() as db:
            registration = IngestionService(db).add_version_to_document(
                document_id=document_id,
                sha256=validated.sha256,
                storage_key=storage_key,
                file_size=validated.file_size,
                mime_type=validated.detected_content_type,
            )

    except Exception:
        with SessionLocal() as db:
            with db.begin():
                upload = db.get(UploadSession, upload_session_id)
                if upload and upload.status == "processing":
                    upload.status = "uploaded"

        logger.exception(
            "Ingestion registration failed for %s",
            upload_session_id,
        )
        raise

    
    # 3.5 Parse and preprocess the original document.

    parsed = parse_rustfs_object(
        storage=storage,
        storage_key=storage_key,
        filename=upload.filename,
    )

    parsed = preprocess_document(parsed)

    parsed_key = (
        f"processed/{document_id}/"
        f"{registration.version_id}/parsed.json"
    )

    storage.put_object(
        storage_key=parsed_key,
        body=json.dumps(
            parsed.to_dict(),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        content_type="application/json",
    )

    logger.info(
        "Parsing completed: version=%s pages=%s elements=%s chars=%s "
        "ocr_review=%s parsed_key=%s",
        registration.version_id,
        parsed.page_count,
        len(parsed.elements),
        parsed.total_characters,
        parsed.needs_ocr_review,
        parsed_key,
    )
    
    # 4. Mark upload as completed.
    with SessionLocal() as db:
        with db.begin():
            upload = db.get(UploadSession, upload_session_id)
            if upload:
                upload.status = "completed"

    logger.info(
        "Upload processed: document=%s version=%s job=%s duplicate=%s",
        registration.document_id,
        registration.version_number,
        registration.job_id,
        registration.duplicate,
    )
