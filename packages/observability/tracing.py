
from langsmith import traceable


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def trace_answer_inputs(inputs):
    inputs = _as_dict(inputs)

    # Do not serialize self, DB sessions or other objects.
    return {
        key: inputs[key]
        for key in ("question", "document_id", "answer_limit")
        if key in inputs
    }


def trace_answer_outputs(output):
    # GeneratedAnswer is a dataclass.
    citations = getattr(output, "citations", [])

    return {
        "abstained": getattr(output, "abstained", None),
        "reason": getattr(output, "reason", None),
        "answer_length": len(getattr(output, "answer", "") or ""),
        "retrieved_count": getattr(output, "retrieved_count", None),
        "citations": [
            {
                "chunk_id": citation.chunk_id,
                "document_id": citation.document_id,
                "version_id": citation.version_id,
                "page_start": citation.page_start,
                "page_end": citation.page_end,
            }
            for citation in citations
        ],
    }


def trace_retrieval_inputs(inputs):
    inputs = _as_dict(inputs)

    return {
        key: inputs[key]
        for key in ("query", "limit", "document_id")
        if key in inputs
    }


def trace_retrieval_outputs(output):
    if not isinstance(output, list):
        return {"result_count": 0}

    return {
        "result_count": len(output),
        "results": [
            {
                "chunk_id": item.get("chunk_id"),
                "parent_id": item.get("parent_id"),
                "retrieval_score": item.get("retrieval_score"),
                "rerank_score": item.get("rerank_score"),
                "page_start": item.get("page_start"),
                "page_end": item.get("page_end"),
            }
            for item in output
        ],
    }


def trace_context_inputs(inputs):
    inputs = _as_dict(inputs)
    results = inputs.get("results", [])

    return {
        "candidate_count": len(results),
        "chunk_ids": [
            item.get("chunk_id")
            for item in results
            if isinstance(item, dict)
        ],
    }


def trace_context_outputs(output):
    sources = getattr(output, "sources", [])

    return {
        "source_count": len(sources),
        "context_length": len(
            getattr(output, "context_text", "") or ""
        ),
        "sources": [
            {
                "number": source.number,
                "chunk_id": source.chunk_id,
                "document_id": source.document_id,
                "page_start": source.page_start,
                "page_end": source.page_end,
            }
            for source in sources
        ],
    }


def trace_generation_inputs(inputs):
    inputs = _as_dict(inputs)
    context = inputs.get("context", "") or ""

    return {
        "question": inputs.get("question"),
        "context_length": len(context),
    }


def trace_generation_outputs(output):
    if not isinstance(output, dict):
        return {"status": "invalid_output"}

    return {
        "abstained": output.get("abstained"),
        "reason": output.get("reason"),
        "answer_length": len(output.get("answer", "")),
        "citation_numbers": output.get("citation_numbers", []),
    }
