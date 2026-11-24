
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceReference:
    number: int
    chunk_id: str
    document_id: str
    version_id: str
    content: str
    heading_path: list[str] = field(default_factory=list)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    retrieval_score: Optional[float] = None
    rerank_score: Optional[float] = None


@dataclass
class BuiltContext:
    context_text: str
    sources: list[SourceReference]


@dataclass
class Citation:
    number: int
    chunk_id: str
    document_id: str
    version_id: str
    heading_path: list[str]
    page_start: Optional[int]
    page_end: Optional[int]
    excerpt: str


@dataclass
class GeneratedAnswer:
    answer: str
    abstained: bool
    reason: Optional[str]
    citations: list[Citation]
    retrieved_count: int
