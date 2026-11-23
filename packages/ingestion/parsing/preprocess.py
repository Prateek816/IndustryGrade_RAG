
import re
import unicodedata

from packages.ingestion.parsing.schemas import ParsedDocument


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)

    # Remove control characters, but preserve tabs and newlines.
    text = "".join(
        char for char in text
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )

    # Normalize whitespace within lines.
    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
    ]

    # Collapse excessive blank lines.
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def preprocess_document(
    document: ParsedDocument,
) -> ParsedDocument:

    processed_elements = []

    for element in document.elements:

        # Remove repeated page furniture from the retrieval body.
        # We retain the page and bounding-box data on all other elements.
        if element.element_type in {
            "page_header",
            "page_footer",
        }:
            continue

        element.text = clean_text(element.text)

        if not element.text:
            continue

        processed_elements.append(element)

    document.elements = processed_elements

    document.full_text = "\n\n".join(
        element.text for element in processed_elements
    )

    document.total_characters = len(document.full_text)

    document.markdown = clean_text(document.markdown)

    return document
