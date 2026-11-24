
from uuid import UUID
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=2,
        max_length=4000,
        description="Question to answer using the indexed documents.",
    )

    # Optional: restrict retrieval to one document.
    document_id: UUID | None = None

    answer_limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of final chunks to use as evidence.",
    )


class CitationResponse(BaseModel):
    number: int
    chunk_id: str
    document_id: str
    version_id: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    abstained: bool
    reason: str | None
    retrieved_count: int
    citations: list[CitationResponse]
