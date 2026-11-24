
import os
import re

from packages.ingestion.retrieval import RetrievalService
from packages.generation.context_builder import ContextBuilder
from packages.generation.answer_generator import AnswerGenerator
from packages.generation.schemas import (
    Citation,
    GeneratedAnswer,
)
from packages.generation.runtime import get_answer_generator


class AnswerService:
    def __init__(self, db):
        self.retrieval = RetrievalService(db)
        self.context_builder = ContextBuilder()
        self.generator = get_answer_generator()

        threshold = os.getenv("RAG_MIN_RERANK_SCORE", "").strip()
        self.min_rerank_score = (
            float(threshold) if threshold else None
        )

    def ask(
        self,
        question: str,
        document_id: str | None = None,
        retrieval_limit: int = 20,
        answer_limit: int = 5,
    ) -> GeneratedAnswer:

        # 1. Retrieve and rerank candidates
        results = self.retrieval.search(
            query=question,
            limit=answer_limit,
            document_id=document_id,
        )

        # Optional calibrated threshold. Disabled by default.
        if self.min_rerank_score is not None:
            results = [
                result
                for result in results
                if result.get("rerank_score") is not None
                and result["rerank_score"] >= self.min_rerank_score
            ]

        # 2. Build numbered context
        built_context = self.context_builder.build(results)

        if not built_context.sources:
            return GeneratedAnswer(
                answer=(
                    "I could not find sufficient information "
                    "in the available documents to answer this question."
                ),
                abstained=True,
                reason="No usable evidence was retrieved.",
                citations=[],
                retrieved_count=len(results),
            )

        # 3. Generate grounded answer
        generated = self.generator.generate(
            question=question,
            context=built_context.context_text,
        )

        # 4. Validate citation references
        source_map = {
            source.number: source
            for source in built_context.sources
        }

        inline_numbers = {
            int(number)
            for number in re.findall(
                r"\[(\d+)\]",
                generated["answer"],
            )
        }

        requested_numbers = set()

        for number in generated["citation_numbers"]:
            try:
                requested_numbers.add(int(number))
            except (TypeError, ValueError):
                continue

        # Include inline citations, but never expose unknown references.
        valid_numbers = (
            requested_numbers | inline_numbers
        ) & set(source_map.keys())

        answer = generated["answer"]

        def remove_invalid_citation(match):
            number = int(match.group(1))
            return match.group(0) if number in valid_numbers else ""

        answer = re.sub(
            r"\[(\d+)\]",
            remove_invalid_citation,
            answer,
        )

        # 5. Construct citation metadata
        citations = []

        if not generated["abstained"]:
            for number in sorted(valid_numbers):
                source = source_map[number]

                citations.append(
                    Citation(
                        number=number,
                        chunk_id=source.chunk_id,
                        document_id=source.document_id,
                        version_id=source.version_id,
                        heading_path=source.heading_path,
                        page_start=source.page_start,
                        page_end=source.page_end,
                        excerpt=source.content,
                    )
                )

        return GeneratedAnswer(
            answer=answer,
            abstained=generated["abstained"],
            reason=generated["reason"],
            citations=citations,
            retrieved_count=len(results),
        )
