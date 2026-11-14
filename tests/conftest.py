
import os

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from packages.core.base import Base

# Import models so they register with Base.metadata
from packages.core.models import (
    Document,
    DocumentVersion,
    IngestionJob,
)
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def test_engine():

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail("TEST_DATABASE_URL is not configured")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )

    # Require a dedicated PostgreSQL test database.
    if engine.dialect.name != "postgresql":
        pytest.fail("Integration tests require PostgreSQL")

    if engine.url.database != "rag_test_db":
        pytest.fail(
            "Refusing to run tests outside rag_test_db"
        )

    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):

    with test_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE "
                "ingestion_jobs, "
                "document_versions, "
                "documents CASCADE"
            )
        )

    SessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def session_factory(test_engine):

    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )
