
import hashlib

from sqlalchemy import select, func

from packages.core.models import (
    Document,
    DocumentVersion,
    IngestionJob,
)

from packages.core.services import IngestionService


def generate_hash(content: str) -> str:
    return hashlib.sha256(
        content.encode()
    ).hexdigest()


def test_create_document(db_session):

    service = IngestionService(db_session)

    result = service.create_document(
        filename="report.pdf",
        title="Annual Report",
        source="upload",
        owner_id="user_123",
        sha256=generate_hash("report content"),
        storage_key="documents/doc1/v1/report.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )

    assert result.version_number == 1
    assert result.duplicate is False
    assert result.job_id is not None

    assert db_session.scalar(
        select(func.count()).select_from(Document)
    ) == 1

    assert db_session.scalar(
        select(func.count()).select_from(DocumentVersion)
    ) == 1

    assert db_session.scalar(
        select(func.count()).select_from(IngestionJob)
    ) == 1


def test_duplicate_upload(db_session):

    service = IngestionService(db_session)

    content_hash = generate_hash("identical document")

    first = service.create_document(
        filename="report.pdf",
        title="Report",
        source="upload",
        owner_id="user_123",
        sha256=content_hash,
        storage_key="documents/doc1/v1/report.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )

    second = service.add_version_to_document(
        document_id=first.document_id,
        sha256=content_hash,
        storage_key="documents/doc1/duplicate/report.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )

    assert second.duplicate is True

    assert second.version_id == first.version_id
    assert second.job_id == first.job_id

    assert db_session.scalar(
        select(func.count()).select_from(DocumentVersion)
    ) == 1

    assert db_session.scalar(
        select(func.count()).select_from(IngestionJob)
    ) == 1


def test_version_numbering(db_session):

    service = IngestionService(db_session)

    first = service.create_document(
        filename="report.pdf",
        title="Report",
        source="upload",
        owner_id="user_123",
        sha256=generate_hash("version one"),
        storage_key="documents/doc1/v1/report.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )

    second = service.add_version_to_document(
        document_id=first.document_id,
        sha256=generate_hash("version two"),
        storage_key="documents/doc1/v2/report.pdf",
        file_size=2048,
        mime_type="application/pdf",
    )

    third = service.add_version_to_document(
        document_id=first.document_id,
        sha256=generate_hash("version three"),
        storage_key="documents/doc1/v3/report.pdf",
        file_size=3072,
        mime_type="application/pdf",
    )

    assert first.version_number == 1
    assert second.version_number == 2
    assert third.version_number == 3


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


def test_concurrent_version_creation(
    db_session,
    session_factory
):

    service = IngestionService(db_session)

    first = service.create_document(
        filename="report.pdf",
        title="Report",
        source="upload",
        owner_id="user_123",
        sha256=generate_hash("original"),
        storage_key="documents/doc1/v1/report.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )

    document_id = first.document_id

    barrier = Barrier(2)

    def upload(content: str):

        # Each worker gets its own database session.
        with session_factory() as session:

            worker_service = IngestionService(session)

            barrier.wait()

            result = worker_service.add_version_to_document(
                document_id=document_id,
                sha256=generate_hash(content),
                storage_key=f"documents/doc1/{content}.pdf",
                file_size=2048,
                mime_type="application/pdf",
            )

            return result.version_number

    with ThreadPoolExecutor(max_workers=2) as executor:

        future_one = executor.submit(
            upload, "concurrent_file_one"
        )

        future_two = executor.submit(
            upload, "concurrent_file_two"
        )

        versions = [
            future_one.result(timeout=30),
            future_two.result(timeout=30),
        ]

    assert sorted(versions) == [2, 3]


def test_concurrent_duplicate_uploads(
    db_session,
    session_factory
):

    service = IngestionService(db_session)

    first = service.create_document(
        filename="report.pdf",
        title="Report",
        source="upload",
        owner_id="user_123",
        sha256=generate_hash("original"),
        storage_key="documents/doc1/v1/report.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )

    document_id = first.document_id
    duplicate_hash = generate_hash("same concurrent content")

    barrier = Barrier(2)

    def upload():

        with session_factory() as session:

            worker_service = IngestionService(session)

            barrier.wait()

            return worker_service.add_version_to_document(
                document_id=document_id,
                sha256=duplicate_hash,
                storage_key="documents/doc1/new.pdf",
                file_size=2048,
                mime_type="application/pdf",
            )

    with ThreadPoolExecutor(max_workers=2) as executor:

        futures = [
            executor.submit(upload),
            executor.submit(upload),
        ]

        results = [
            future.result(timeout=30)
            for future in futures
        ]

    assert all(result.version_id == results[0].version_id
               for result in results)

    assert sum(result.duplicate for result in results) == 1

    assert db_session.scalar(
        select(func.count()).select_from(DocumentVersion)
    ) == 2

    assert db_session.scalar(
        select(func.count()).select_from(IngestionJob)
    ) == 2


