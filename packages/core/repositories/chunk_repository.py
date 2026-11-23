
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from packages.core.models import Chunk


class ChunkRepository:

    def __init__(self, db: Session):
        self.db = db

    def upsert_many(self, rows: list[dict]):

        if not rows:
            return

        statement = insert(Chunk).values(rows)

        update_fields = [
            "document_id",
            "version_id",
            "parent_id",
            "chunk_type",
            "chunk_index",
            "content",
            "token_count",
            "page_start",
            "page_end",
            "heading_path",
            "source_element_ids",
        ]

        statement = statement.on_conflict_do_update(
            index_elements=[Chunk.id],
            set_={
                field: getattr(statement.excluded, field)
                for field in update_fields
            },
        )

        self.db.execute(statement)
