
from uuid import UUID

from pydantic import BaseModel, Field


class UploadInitiateRequest(BaseModel):
    filename: str
    content_type: str
    title: str | None = None
    source: str = "upload"
    expected_size: int | None = Field(default=None, gt=0)


class UploadInitiateResponse(BaseModel):
    document_id: UUID
    upload_session_id: UUID
    upload_url: str
    method: str
    required_headers: dict[str, str]
    expires_in: int


class UploadCompleteResponse(BaseModel):
    document_id: UUID
    upload_session_id: UUID
    status: str
