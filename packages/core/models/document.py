
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    ForeignKeyConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.base import Base


class Document(Base):

    __tablename__ = "documents"

    __table_args__ = (
        ForeignKeyConstraint(
            ["current_version_id", "id"],
            [
                "document_versions.id",
                "document_versions.document_id"
            ],
            name="fk_document_current_version",
            use_alter=True
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )

    title: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    owner_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
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

    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        foreign_keys="DocumentVersion.document_id"
    )

    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="document",
        foreign_keys="IngestionJob.document_id"
    )

    upload_sessions = relationship(
        "UploadSession",
        back_populates="document",
        cascade="all, delete-orphan",
    )
