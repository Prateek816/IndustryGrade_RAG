
import os

import numpy as np
import torch

from sentence_transformers import SentenceTransformer


class EmbeddingService:

    def __init__(self):
        model_name = os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )

        if torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

        self.model = SentenceTransformer(
            model_name,
            device=device,
        )

        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> np.ndarray:

        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return vectors.astype(np.float32)
