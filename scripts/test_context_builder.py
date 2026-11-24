import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.generation.context_builder import ContextBuilder


def main():
    builder = ContextBuilder()

    results = [
        {
            "chunk_id": "chunk-1",
            "content": "The first phase is project selection.",
            "heading_path": ["Introduction", "Phases"],
            "page_start": 1,
            "page_end": 1,
            "document_id": "doc-1",
            "version_id": "version-1",
            "rerank_score": 5.2,
        },
        {
            "chunk_id": "chunk-2",
            "content": "The second phase is proposal submission.",
            "heading_path": ["Introduction", "Phases"],
            "page_start": 2,
            "page_end": 2,
            "document_id": "doc-1",
            "version_id": "version-1",
            "rerank_score": 4.8,
        },
    ]

    context = builder.build(results)

    assert len(context.sources) == 2
    assert "[1]" in context.context_text
    assert "[2]" in context.context_text

    assert context.sources[0].chunk_id == "chunk-1"
    assert context.sources[1].page_start == 2

    print("ContextBuilder tests passed.")
    print(context.context_text)


if __name__ == "__main__":
    main()
