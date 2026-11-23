
import os
from functools import lru_cache

import numpy as np
import torch
from sentence_transformers import CrossEncoder


def get_device() -> str:
    configured = os.getenv("RERANKER_DEVICE", "auto").lower()

    if configured != "auto":
        return configured

    if torch.backends.mps.is_available():
        return "mps"

    if torch.cuda.is_available():
        return "cuda"

    return "cpu"


@lru_cache(maxsize=1)
def load_cross_encoder(model_name: str, device: str):
    """Load the model once and reuse it across requests."""
    return CrossEncoder(
        model_name,
        device=device,
        max_length=512,
    )


class CrossEncoderReranker:
    def __init__(self):
        self.model_name = os.getenv(
            "RERANKER_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        )

        self.batch_size = int(
            os.getenv("RERANKER_BATCH_SIZE", "16")
        )

        self.device = get_device()

        self.model = load_cross_encoder(
            self.model_name,
            self.device,
        )

    def rerank(self, query: str, candidates: list[dict], top_k: int = 5):
        if not candidates:
            return []

        pairs = []

        for candidate in candidates:
            heading = " > ".join(
                candidate.get("heading_path") or []
            )

            content = candidate.get("content", "")

            document_text = f"{heading}\n\n{content}".strip()

            pairs.append((query, document_text))

        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        scores = np.asarray(scores).reshape(-1)

        reranked = []

        for candidate, score in zip(candidates, scores):
            result = dict(candidate)

            # This is a relevance score, not a probability.
            result["rerank_score"] = float(score)

            reranked.append(result)

        reranked.sort(
            key=lambda item: item["rerank_score"],
            reverse=True,
        )

        return reranked[:top_k]
