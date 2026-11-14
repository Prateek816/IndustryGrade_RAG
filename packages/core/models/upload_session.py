
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.base import Base


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'uploaded', 'processing', "
            "'completed', 'rejected', 'expired')",
            name="ck_upload_sessions_status",
        ),
        CheckConstraint(
            "expected_size IS NULL OR expected_size > 0",
            name="ck_upload_sessions_expected_size_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Object's unique location in RustFS
    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
    )

    # Original upload information
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expected_content_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # Optional because the client may not provide it
    expected_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    uploaded_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document = relationship(
        "Document",
        back_populates="upload_sessions",
    )
