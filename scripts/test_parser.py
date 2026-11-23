
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.ingestion.parsing.docling_parser import DoclingParser
from packages.ingestion.parsing.preprocess import preprocess_document

if len(sys.argv) < 2:
    raise SystemExit(
        "Usage: python scripts/test_parser.py <document_path>"
    )

file_path = sys.argv[1]

parser = DoclingParser()

parsed = parser.parse(
    file_path=file_path,
    filename=file_path.split("/")[-1],
)

parsed = preprocess_document(parsed)

print("Pages:", parsed.page_count)
print("Elements:", len(parsed.elements))
print("Characters:", parsed.total_characters)
print("Needs OCR review:", parsed.needs_ocr_review)

for element in parsed.elements[:10]:
    print(
        element.element_type,
        element.page_number,
        element.heading_path,
        element.text[:150],
    )

with open("parsed_output.json", "w", encoding="utf-8") as f:
    json.dump(
        parsed.to_dict(),
        f,
        ensure_ascii=False,
        indent=2,
    )

print("\nSaved parsed_output.json")
