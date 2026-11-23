
import json
import sys
import uuid
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.ingestion.parsing.schemas import (
    ParsedDocument,
    DocumentElement,
    BoundingBox,
)
from packages.ingestion.chunking.chunker import StructureAwareChunker


with open("parsed_output.json", encoding="utf-8") as file:
    data = json.load(file)

elements = []

for item in data["elements"]:
    bbox = item.get("bbox")

    elements.append(
        DocumentElement(
            element_id=item["element_id"],
            element_type=item["element_type"],
            text=item["text"],
            page_number=item["page_number"],
            bbox=BoundingBox(**bbox) if bbox else None,
            heading_path=item["heading_path"],
            metadata=item["metadata"],
        )
    )

document = ParsedDocument(
    filename=data["filename"],
    page_count=data["page_count"],
    elements=elements,
    full_text=data["full_text"],
    markdown=data["markdown"],
    total_characters=data["total_characters"],
    needs_ocr_review=data["needs_ocr_review"],
)

version_id = uuid.uuid4()

chunker = StructureAwareChunker(
    chunk_size=400,
    chunk_overlap=60,
)

result = chunker.chunk(document, version_id)

print("Parent sections:", len(result.parents))
print("Child chunks:", len(result.children))

for child in result.children[:10]:
    print("\n--------------------------")
    print("ID:", child.id)
    print("Parent:", child.parent_id)
    print("Tokens:", child.token_count)
    print("Pages:", child.page_start, "-", child.page_end)
    print("Heading:", " > ".join(child.heading_path))
    print("Text:", child.content[:300])

output = {
    "parents": [
        {
            **vars(parent),
            "id": str(parent.id),
            "version_id": str(parent.version_id),
            "child_ids": [str(x) for x in parent.child_ids],
        }
        for parent in result.parents
    ],
    "children": [
        {
            **vars(child),
            "id": str(child.id),
            "parent_id": str(child.parent_id),
            "version_id": str(child.version_id),
        }
        for child in result.children
    ],
}

with open("chunked_output.json", "w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

print("\nSaved chunked_output.json")
