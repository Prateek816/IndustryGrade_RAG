
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class ParentChunk:
    id: UUID
    version_id: UUID
    heading_path: list[str]
    content: str
    page_start: int | None
    page_end: int | None
    child_ids: list[UUID] = field(default_factory=list)


@dataclass
class ChildChunk:
    id: UUID
    parent_id: UUID
    version_id: UUID
    content: str
    token_count: int
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    source_element_ids: list[str] = field(default_factory=list)


@dataclass
class ChunkingResult:
    parents: list[ParentChunk]
    children: list[ChildChunk]
