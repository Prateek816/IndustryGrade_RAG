
import os

from packages.generation.schemas import (
    BuiltContext,
    SourceReference,
)
from langsmith import traceable

from packages.observability.tracing import (
    trace_context_inputs,
    trace_context_outputs,
)

class ContextBuilder:
    def __init__(self):
        self.max_chunks = int(
            os.getenv("RAG_MAX_CONTEXT_CHUNKS", "8")
        )

        self.max_chars = int(
            os.getenv("RAG_MAX_CONTEXT_CHARS", "18000")
        )
    @traceable(
        name="context_builder",
        run_type="chain",
        process_inputs=trace_context_inputs,
        process_outputs=trace_context_outputs,
        tags=["powerful-rag", "context"],
    )
    def build(self, results: list[dict]) -> BuiltContext:
        sources = []
        context_parts = []
        used_chars = 0

        seen_chunks = set()

        for result in results:
            chunk_id = str(result.get("chunk_id", ""))

            if not chunk_id or chunk_id in seen_chunks:
                continue

            content = (result.get("content") or "").strip()

            if not content:
                continue

            # Keep the actual child chunk as citation evidence.
            # Parent content is useful context but may contain
            # material not directly represented by this chunk.
            heading_path = result.get("heading_path") or []

            remaining = self.max_chars - used_chars

            if remaining <= 0:
                break

            content = content[:remaining]

            source_number = len(sources) + 1

            source = SourceReference(
                number=source_number,
                chunk_id=chunk_id,
                document_id=str(result.get("document_id") or ""),
                version_id=str(result.get("version_id") or ""),
                content=content,
                heading_path=heading_path,
                page_start=result.get("page_start"),
                page_end=result.get("page_end"),
                retrieval_score=result.get("retrieval_score"),
                rerank_score=result.get("rerank_score"),
            )

            heading = " > ".join(heading_path) or "Untitled section"

            source_text = (
                f"[{source_number}]\n"
                f"Chunk ID: {chunk_id}\n"
                f"Section: {heading}\n"
                f"Pages: {source.page_start or 'Unknown'}"
                f"-{source.page_end or source.page_start or 'Unknown'}\n"
                f"Content:\n{content}\n"
            )

            context_parts.append(source_text)
            sources.append(source)

            used_chars += len(content)
            seen_chunks.add(chunk_id)

            if len(sources) >= self.max_chunks:
                break

        return BuiltContext(
            context_text="\n\n---\n\n".join(context_parts),
            sources=sources,
        )
