import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.core.database import SessionLocal
from packages.generation import AnswerService


QUESTIONS = [
    "What are the phases of the capstone assignment?",
    "What is a Letter of Intent?",
    "What is the exact deadline for submission?",
    "Who is the president of the United States?",
]


def main():
    db = SessionLocal()

    try:
        service = AnswerService(db)

        for question in QUESTIONS:
            print("\n" + "=" * 80)
            print("QUESTION:", question)

            result = service.ask(question)

            print("\nANSWER:")
            print(result.answer)

            print("\nABSTAINED:", result.abstained)
            print("REASON:", result.reason)
            print("RETRIEVED:", result.retrieved_count)

            print("\nCITATIONS:")

            for citation in result.citations:
                heading = " > ".join(citation.heading_path)

                print({
                    "citation": citation.number,
                    "chunk_id": citation.chunk_id,
                    "document_id": citation.document_id,
                    "version_id": citation.version_id,
                    "heading": heading,
                    "pages": (
                        citation.page_start,
                        citation.page_end,
                    ),
                })

    finally:
        db.close()


if __name__ == "__main__":
    main()
