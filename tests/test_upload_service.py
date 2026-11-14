
import uuid

import pytest
from sqlalchemy import select

from packages.core.models import Document, UploadSession
from packages.core.services.upload_service import (
    UploadService,
    UploadValidationError,
)


class FakeStorage:

    def generate_presigned_upload_url(
        self,
        storage_key,
        content_type,
        expiry=900,
    ):
        return f"https://rustfs.test/{storage_key}?signature=test"


def test_initiate_upload(db_session):

    service = UploadService(
        db_session,
        storage=FakeStorage(),
    )

    owner_id = uuid.uuid4()

    result = service.initiate_upload(
        filename="research.pdf",
        content_type="application/pdf",
        owner_id=owner_id,
        expected_size=1024,
    )

    document = db_session.get(Document, result.document_id)

    upload_session = db_session.get(
        UploadSession,
        result.upload_session_id,
    )

    assert document is not None
    assert document.filename == "research.pdf"
    assert uuid.UUID(str(document.owner_id)) == owner_id

    assert upload_session is not None
    assert upload_session.document_id == document.id
    assert upload_session.status == "pending"
    assert upload_session.expected_size == 1024

    assert result.method == "PUT"
    assert result.upload_url.startswith("https://rustfs.test/")
    assert result.required_headers["Content-Type"] == "application/pdf"


def test_reject_oversized_upload(db_session):

    service = UploadService(
        db_session,
        storage=FakeStorage(),
    )

    with pytest.raises(UploadValidationError):

        service.initiate_upload(
            filename="large.pdf",
            content_type="application/pdf",
            owner_id=uuid.uuid4(),
            expected_size=100 * 1024 * 1024,
        )

    documents = db_session.scalars(
        select(Document)
    ).all()

    assert len(documents) == 0
