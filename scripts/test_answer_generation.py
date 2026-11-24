import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from packages.generation.answer_generator import AnswerGenerator


def main():
    generator = AnswerGenerator()

    context = """
[1]
Section: Capstone > Phases
Pages: 1-1
Content:
The first phase of the capstone assignment is project selection.

[2]
Section: Capstone > Submission
Pages: 2-2
Content:
Students must submit a Letter of Intent before beginning the project.
"""

    questions = [
        "What is the first phase of the capstone assignment?",
        "What is a Letter of Intent?",
        "What is the exact deadline for submission?",
    ]

    for question in questions:
        print("\n" + "=" * 70)
        print("QUESTION:", question)

        result = generator.generate(
            question=question,
            context=context,
        )

        print("ANSWER:", result["answer"])
        print("ABSTAINED:", result["abstained"])
        print("REASON:", result["reason"])
        print("CITATIONS:", result["citation_numbers"])


if __name__ == "__main__":
    main()
