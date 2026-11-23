
import uuid

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.base import Base


class Chunk(Base):
    __tablename__ = "chunks"

    __table_args__ = (
        ForeignKeyConstraint(
            ["version_id", "document_id"],
            ["document_versions.id", "document_versions.document_id"],
            name="fk_chunks_version_document",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "version_id",
            "chunk_type",
            "chunk_index",
            name="uq_chunks_version_type_index",
        ),
        CheckConstraint(
            "chunk_type IN ('parent', 'child')",
            name="ck_chunks_type",
        ),
        CheckConstraint(
            "(chunk_type = 'parent' AND parent_id IS NULL) OR "
            "(chunk_type = 'child' AND parent_id IS NOT NULL)",
            name="ck_chunks_parent_relationship",
        ),
        CheckConstraint(
            "token_count >= 0",
            name="ck_chunks_token_count",
        ),
        CheckConstraint(
            "page_start IS NULL OR page_end IS NULL "
            "OR page_end >= page_start",
            name="ck_chunks_page_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    chunk_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    page_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    page_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    heading_path: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    source_element_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
