CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    filename VARCHAR(512) NOT NULL,
    title VARCHAR(512),

    source VARCHAR(50) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,

    current_version_id UUID,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    version_number INTEGER NOT NULL,

    sha256 CHAR(64) NOT NULL,

    storage_key TEXT NOT NULL,

    file_size BIGINT NOT NULL,

    mime_type VARCHAR(100) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'pending',

    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_document_version
        UNIQUE (document_id, version_number),

    CONSTRAINT valid_version_number
        CHECK (version_number > 0),

    CONSTRAINT valid_file_size
        CHECK (file_size > 0),

    CONSTRAINT valid_sha256
        CHECK (sha256 ~ '^[a-fA-F0-9]{64}$'),

    CONSTRAINT valid_version_status
        CHECK (status IN (
            'pending',
            'processing',
            'active',
            'failed',
            'superseded'
        ))
);

CREATE UNIQUE INDEX unique_active_version_per_document
ON document_versions(document_id)
WHERE is_active = TRUE;

CREATE INDEX idx_versions_document_id
ON document_versions(document_id);

CREATE INDEX idx_versions_sha256
ON document_versions(sha256);


CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    version_id UUID NOT NULL
        REFERENCES document_versions(id)
        ON DELETE CASCADE,

    status VARCHAR(30) NOT NULL DEFAULT 'queued',

    current_stage VARCHAR(50) NOT NULL DEFAULT 'validation',

    retry_count INTEGER NOT NULL DEFAULT 0,

    max_retries INTEGER NOT NULL DEFAULT 3,

    error_message TEXT,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_job_status
        CHECK (status IN (
            'queued',
            'running',
            'completed',
            'failed',
            'cancelled'
        )),

    CONSTRAINT valid_retry_count
        CHECK (retry_count >= 0 AND max_retries >= 0),

    CONSTRAINT valid_job_dates
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        ),

    CONSTRAINT unique_job_per_version
        UNIQUE (version_id)
);

CREATE INDEX idx_ingestion_jobs_status
ON ingestion_jobs(status);

CREATE INDEX idx_ingestion_jobs_document
ON ingestion_jobs(document_id);

CREATE INDEX idx_ingestion_jobs_created
ON ingestion_jobs(created_at);

