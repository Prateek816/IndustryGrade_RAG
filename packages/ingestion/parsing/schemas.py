
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float


@dataclass
class DocumentElement:
    element_id: str
    element_type: str
    text: str
    page_number: int | None = None
    bbox: BoundingBox | None = None
    heading_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedDocument:
    filename: str
    page_count: int
    elements: list[DocumentElement]
    full_text: str
    markdown: str
    total_characters: int
    needs_ocr_review: bool

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "page_count": self.page_count,
            "elements": [e.to_dict() for e in self.elements],
            "full_text": self.full_text,
            "markdown": self.markdown,
            "total_characters": self.total_characters,
            "needs_ocr_review": self.needs_ocr_review,
        }
