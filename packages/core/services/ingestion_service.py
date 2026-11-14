
import re
import uuid

from dataclasses import dataclass
from sqlalchemy.orm import Session

from packages.core.models import (
    Document,
    DocumentVersion,
    IngestionJob,
)

from packages.core.repositories import (
    DocumentRepository,
    VersionRepository,
    JobRepository,
)


@dataclass(frozen=True)
class IngestionRegistration:
    document_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID | None
    version_number: int
    duplicate: bool


class DocumentNotFoundError(Exception):
    pass


class IngestionService:

    def __init__(self, db: Session):

        self.db = db

        self.document_repo = DocumentRepository(db)
        self.version_repo = VersionRepository(db)
        self.job_repo = JobRepository(db)

    def create_document(
        self,
        filename: str,
        title: str | None,
        source: str,
        owner_id: str,
        sha256: str,
        storage_key: str,
        file_size: int,
        mime_type: str,
    ) -> IngestionRegistration:

        with self.db.begin():

            document = Document(
                filename=filename,
                title=title,
                source=source,
                owner_id=owner_id,
            )

            self.document_repo.create(document)

            return self._register_version_and_job(
                document=document,
                sha256=sha256,
                storage_key=storage_key,
                file_size=file_size,
                mime_type=mime_type,
            )

    def add_version_to_document(
        self,
        document_id: uuid.UUID,
        sha256: str,
        storage_key: str,
        file_size: int,
        mime_type: str,
    ) -> IngestionRegistration:

        with self.db.begin():

            document = self.document_repo.get_by_id_for_update(
                document_id
            )

            if document is None:
                raise DocumentNotFoundError(
                    f"Document {document_id} not found"
                )

            return self._register_version_and_job(
                document=document,
                sha256=sha256,
                storage_key=storage_key,
                file_size=file_size,
                mime_type=mime_type,
            )

    def _register_version_and_job(
        self,
        document: Document,
        sha256: str,
        storage_key: str,
        file_size: int,
        mime_type: str,
    ) -> IngestionRegistration:

        sha256 = sha256.strip().lower()

        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise ValueError("Invalid SHA-256 hash")

        if file_size <= 0:
            raise ValueError("File size must be positive")

        
        existing_version = self.version_repo.get_by_hash(
            document.id,
            sha256,
        )

        if existing_version is not None:

            existing_job = self.job_repo.get_by_version(
                existing_version.id
            )

            return IngestionRegistration(
                document_id=document.id,
                version_id=existing_version.id,
                job_id=existing_job.id if existing_job else None,
                version_number=existing_version.version_number,
                duplicate=True,
            )

        # 2. Calculate the next version number.
        latest_version = self.version_repo.get_latest_version_number(
            document.id
        )

        next_version_number = latest_version + 1

        # 3. Create the new version.
        version = DocumentVersion(
            document_id=document.id,
            version_number=next_version_number,
            sha256=sha256,
            storage_key=storage_key,
            file_size=file_size,
            mime_type=mime_type,
            status="pending",
            is_active=False,
        )

        self.version_repo.create(version)

        # 4. Create the ingestion job.
        job = IngestionJob(
            document_id=document.id,
            version_id=version.id,
            status="queued",
            current_stage="validation",
            retry_count=0,
            max_retries=3,
        )

        self.job_repo.create(job)

        # 5. Return registration result.
        return IngestionRegistration(
            document_id=document.id,
            version_id=version.id,
            job_id=job.id,
            version_number=next_version_number,
            duplicate=False,
        )
