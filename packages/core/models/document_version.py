
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    BigInteger,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.base import Base


class DocumentVersion(Base):

    __tablename__ = "document_versions"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="unique_document_version"
        ),

        # Required as the target of composite foreign keys.
        UniqueConstraint(
            "id",
            "document_id",
            name="unique_version_document_pair"
        ),

        CheckConstraint(
            "version_number > 0",
            name="valid_version_number"
        ),

        CheckConstraint(
            "file_size > 0",
            name="valid_file_size"
        ),

        CheckConstraint(
            "sha256 ~ '^[a-fA-F0-9]{64}$'",
            name="valid_sha256"
        ),

        CheckConstraint(
            "status IN ('pending', 'processing', 'active', 'failed', 'superseded')",
            name="valid_version_status"
        ),

        Index(
            "unique_active_version_per_document",
            "document_id",
            unique=True,
            postgresql_where=text("is_active = TRUE")
        ),

        Index(
            "idx_versions_sha256",
            "sha256"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    storage_key: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default=text("'pending'")
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="versions",
        foreign_keys=[document_id]
    )

    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="version",
        foreign_keys="IngestionJob.version_id"
    )
