
import uuid

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.base import Base
from sqlalchemy.orm import relationship

class Document(Base):

    __tablename__ = "documents"

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

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    ingestion_jobs = relationship(
        "IngestionJob",
        back_populates="document"
    )
