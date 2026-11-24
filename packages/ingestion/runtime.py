
from functools import lru_cache

from packages.ingestion.embedding.embedder import EmbeddingService
from packages.ingestion.embedding.sparse_embedder import SparseEmbeddingService
from packages.ingestion.vector_store import QdrantVectorStore
from packages.ingestion.reranking import CrossEncoderReranker


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_sparse_embedding_service() -> SparseEmbeddingService:
    return SparseEmbeddingService()


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore()


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


def clear_runtime_cache():
    """Useful for tests and controlled model reloads."""
    get_embedding_service.cache_clear()
    get_sparse_embedding_service.cache_clear()
    get_vector_store.cache_clear()
    get_reranker.cache_clear()
