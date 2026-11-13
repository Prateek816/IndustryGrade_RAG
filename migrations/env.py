
from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from dotenv import load_dotenv

from packages.core.base import Base

# Load all ORM models into Base.metadata
from packages.core.models import (
    Document,
    DocumentVersion,
    IngestionJob,
)

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Read database URL from environment
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is missing")

# Override URL from alembic.ini
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%")
)

# SQLAlchemy metadata
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations without creating a database connection."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations using a live database connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
