
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.models import IngestionJob


class JobRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, job: IngestionJob) -> IngestionJob:
        self.db.add(job)
        self.db.flush()
        return job

    def get_by_id(
        self,
        job_id: uuid.UUID
    ) -> IngestionJob | None:

        query = select(IngestionJob).where(
            IngestionJob.id == job_id
        )

        return self.db.scalar(query)

    def get_by_version(
        self,
        version_id: uuid.UUID
    ) -> IngestionJob | None:

        query = select(IngestionJob).where(
            IngestionJob.version_id == version_id
        )

        return self.db.scalar(query)

    def update_status(
        self,
        job: IngestionJob,
        status: str
    ) -> IngestionJob:

        job.status = status

        self.db.flush()

        return job

    def update_stage(
        self,
        job: IngestionJob,
        stage: str
    ) -> IngestionJob:

        job.current_stage = stage

        self.db.flush()

        return job

    def increment_retry(self, job: IngestionJob) -> IngestionJob:

        if job.retry_count >= job.max_retries:
            raise ValueError("Maximum retry count exceeded")

        job.retry_count += 1

        self.db.flush()

        return job
