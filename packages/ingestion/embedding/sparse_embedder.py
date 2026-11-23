
from fastembed import SparseTextEmbedding


class SparseEmbeddingService:

    def __init__(self):
        self.model = SparseTextEmbedding(
            model_name="Qdrant/bm25"
        )

    def embed(self, texts: list[str]):
        if not texts:
            return []

        return list(
            self.model.embed(
                texts,
                batch_size=32,
            )
        )
