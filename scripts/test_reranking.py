

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.core.database import SessionLocal
from packages.ingestion.retrieval import RetrievalService


QUERIES = [
    "What are the phases of the capstone assignment?",
    "What is a Letter of Intent?",
    "What are the responsibilities of the actors?",
    "How should AI be used in the assignment?",
]


def main():
    db = SessionLocal()

    try:
        retrieval = RetrievalService(db)

        for query in QUERIES:
            print("\n" + "=" * 80)
            print(f"QUERY: {query}")
            print("=" * 80)

            results = retrieval.search(
                query=query,
                candidate_limit=20,
                limit=5,
            )

            for index, result in enumerate(results, start=1):
                print(f"\nRank: {index}")
                print(f"Rerank score: {result['rerank_score']:.4f}")
                print(
                    f"Original RRF score: "
                    f"{result['retrieval_score']:.4f}"
                )
                print(f"Heading: {' > '.join(result['heading_path'])}")
                print(f"Content: {result['content'][:500]}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
