
from uuid import UUID, uuid5, NAMESPACE_URL

import tiktoken

from packages.ingestion.parsing.schemas import ParsedDocument
from packages.ingestion.chunking.schemas import (
    ParentChunk,
    ChildChunk,
    ChunkingResult,
)


class StructureAwareChunker:

    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 60,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("Invalid chunk overlap")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _group_sections(self, document: ParsedDocument):
        sections = []
        current = None

        for element in document.elements:
            heading_path = element.heading_path or ["Untitled"]

            # Start a new section when the heading path changes.
            if current is None or current["heading_path"] != heading_path:
                current = {
                    "heading_path": heading_path.copy(),
                    "elements": [],
                }
                sections.append(current)

            current["elements"].append(element)

        return sections

    def _tokenize_section(self, elements):
        tokens = []
        token_sources = []

        for element in elements:
            element_tokens = self.tokenizer.encode(element.text)

            if not element_tokens:
                continue

            # Add a separator between source elements.
            separator = self.tokenizer.encode("\n\n")

            tokens.extend(separator)
            token_sources.extend(
                [element.element_id] * len(separator)
            )

            tokens.extend(element_tokens)
            token_sources.extend(
                [element.element_id] * len(element_tokens)
            )

        return tokens, token_sources

    def chunk(
        self,
        document: ParsedDocument,
        version_id: UUID,
    ) -> ChunkingResult:

        parents = []
        children = []

        sections = self._group_sections(document)

        for section_index, section in enumerate(sections):

            elements = section["elements"]
            heading_path = section["heading_path"]

            section_text = "\n\n".join(
                element.text for element in elements
            ).strip()

            if not section_text:
                continue

            parent_id = uuid5(
                NAMESPACE_URL,
                f"{version_id}:parent:{section_index}",
            )

            pages = [
                element.page_number
                for element in elements
                if element.page_number is not None
            ]

            parent = ParentChunk(
                id=parent_id,
                version_id=version_id,
                heading_path=heading_path,
                content=section_text,
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
            )

            tokens, token_sources = self._tokenize_section(elements)

            if not tokens:
                continue

            start = 0
            child_index = 0

            while start < len(tokens):

                end = min(
                    start + self.chunk_size,
                    len(tokens),
                )

                chunk_tokens = tokens[start:end]

                content = self.tokenizer.decode(chunk_tokens)

                chunk_id = uuid5(
                    NAMESPACE_URL,
                    f"{version_id}:parent:{section_index}:child:{child_index}",
                )

                source_ids = list(dict.fromkeys(
                    token_sources[start:end]
                ))

                source_elements = [
                    element for element in elements
                    if element.element_id in source_ids
                ]

                child_pages = [
                    element.page_number
                    for element in source_elements
                    if element.page_number is not None
                ]

                child = ChildChunk(
                    id=chunk_id,
                    parent_id=parent_id,
                    version_id=version_id,
                    content=content.strip(),
                    token_count=len(chunk_tokens),
                    page_start=min(child_pages) if child_pages else None,
                    page_end=max(child_pages) if child_pages else None,
                    heading_path=heading_path.copy(),
                    source_element_ids=source_ids,
                )

                children.append(child)
                parent.child_ids.append(chunk_id)

                child_index += 1

                if end == len(tokens):
                    break

                start = end - self.chunk_overlap

            parents.append(parent)

        return ChunkingResult(
            parents=parents,
            children=children,
        )
