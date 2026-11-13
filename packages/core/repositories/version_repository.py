
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from packages.core.models import DocumentVersion


class VersionRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, version: DocumentVersion) -> DocumentVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_by_id(
        self,
        version_id: uuid.UUID
    ) -> DocumentVersion | None:

        query = select(DocumentVersion).where(
            DocumentVersion.id == version_id
        )

        return self.db.scalar(query)

    def get_by_hash(
        self,
        document_id: uuid.UUID,
        sha256: str
    ) -> DocumentVersion | None:

        query = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.sha256 == sha256
        )

        return self.db.scalar(query)

    def get_latest_version_number(
        self,
        document_id: uuid.UUID
    ) -> int:

        query = select(
            func.max(DocumentVersion.version_number)
        ).where(
            DocumentVersion.document_id == document_id
        )

        result = self.db.scalar(query)

        return result or 0

    def get_all_versions(
        self,
        document_id: uuid.UUID
    ) -> list[DocumentVersion]:

        query = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )

        return list(self.db.scalars(query).all())
