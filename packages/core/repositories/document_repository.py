import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.models import Document


class DocumentRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        query = select(Document).where(
            Document.id == document_id
        )

        return self.db.scalar(query)

    def get_by_owner(
        self,
        owner_id: str
    ) -> list[Document]:

        query = select(Document).where(
            Document.owner_id == owner_id
        )

        return list(self.db.scalars(query).all())
    
    def get_by_id_for_update(
        self,
        document_id: uuid.UUID
    ) -> Document | None:

        query = (
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
        )

        return self.db.scalar(query)