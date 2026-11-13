
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.base import Base


class IngestionJob(Base):

    __tablename__ = "ingestion_jobs"

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            name="unique_job_per_version"
        ),

        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="valid_job_status"
        ),

        CheckConstraint(
            "current_stage IN ('validation', 'parsing', 'preprocessing', "
            "'chunking', 'contextualization', 'embedding', 'indexing', "
            "'graph_extraction', 'validation_activation')",
            name="valid_job_stage"
        ),

        CheckConstraint(
            "retry_count >= 0 AND max_retries >= 0 "
            "AND retry_count <= max_retries",
            name="valid_retry_count"
        ),

        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL "
            "OR completed_at >= started_at",
            name="valid_job_dates"
        ),

        ForeignKeyConstraint(
            ["version_id", "document_id"],
            [
                "document_versions.id",
                "document_versions.document_id"
            ],
            name="fk_job_document_version",
            ondelete="CASCADE"
        ),

        Index(
            "idx_ingestion_jobs_status_created",
            "status",
            "created_at"
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

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default=text("'queued'")
    )

    current_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="validation",
        server_default=text("'validation'")
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0")
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=text("3")
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="ingestion_jobs",
        foreign_keys=[document_id]
    )

    version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion",
        back_populates="ingestion_jobs",
        foreign_keys=[version_id]
    )
