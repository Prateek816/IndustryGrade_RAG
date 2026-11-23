import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.core.database import SessionLocal
from packages.ingestion.retrieval import RetrievalService


queries = [
    "What are the phases of the capstone assignment?",
    "Letter of Intent LOI",
    "What should actors do in the protocol?",
    "How should AI be used in the assignment?",
]


with SessionLocal() as db:

    retriever = RetrievalService(db)

    for query in queries:

        print("\n" + "=" * 70)
        print("QUERY:", query)
        print("=" * 70)

        results = retriever.search(
            query=query,
            limit=5,
        )

        for index, result in enumerate(results, start=1):

            print(f"\nResult {index}")
            print("RRF score:", result["score"])
            print("Heading:", " > ".join(result["heading_path"]))
            print("Page:", result["page_start"], "-", result["page_end"])
            print("Child:", result["content"][:350])
            print(
                "Parent:",
                (result["parent_content"] or "")[:350],
            )
