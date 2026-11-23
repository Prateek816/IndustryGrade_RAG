
from sqlalchemy import select

from packages.core.models.chunk import Chunk
from packages.ingestion.embedding.embedder import EmbeddingService
from packages.ingestion.embedding.sparse_embedder import SparseEmbeddingService
from packages.ingestion.vector_store import QdrantVectorStore
from packages.ingestion.reranking import CrossEncoderReranker


class RetrievalService:
    def __init__(self, db):
        self.db = db

        self.embedder = EmbeddingService()
        self.sparse_embedder = SparseEmbeddingService()
        self.vector_store = QdrantVectorStore()

        self.reranker = CrossEncoderReranker()

    def search(
        self,
        query: str,
        limit: int = 5,
        document_id: str | None = None,
        candidate_limit: int = 20,
    ):
        # Stage 1: Dense retrieval
        dense_vector = self.embedder.embed([query])[0]

        # Stage 2: Sparse retrieval
        sparse_vector = self.sparse_embedder.embed([query])[0]

        # Stage 3: Hybrid retrieval with RRF
        candidates = self.vector_store.hybrid_search(
            dense_vector=dense_vector.tolist(),
            sparse_indices=sparse_vector.indices.tolist(),
            sparse_values=sparse_vector.values.tolist(),
            limit=max(candidate_limit, limit),
            document_id=document_id,
        )

        if not candidates:
            return []

        # Stage 4: Fetch parent chunks from PostgreSQL
        parent_ids = {
            point.payload.get("parent_id")
            for point in candidates
            if point.payload and point.payload.get("parent_id")
        }

        parent_map = {}

        if parent_ids:
            parent_chunks = self.db.scalars(
                select(Chunk).where(
                    Chunk.id.in_(parent_ids),
                    Chunk.chunk_type == "parent",
                )
            ).all()

            parent_map = {
                str(chunk.id): chunk.content
                for chunk in parent_chunks
            }

        # Convert Qdrant points into candidate dictionaries
        candidate_results = []

        for point in candidates:
            payload = point.payload or {}

            parent_id = payload.get("parent_id")

            candidate_results.append({
                "chunk_id": str(point.id),
                "parent_id": parent_id,
                "retrieval_score": float(point.score),
                "content": payload.get("content", ""),
                "parent_content": parent_map.get(parent_id),
                "heading_path": payload.get("heading_path", []),
                "page_start": payload.get("page_start"),
                "page_end": payload.get("page_end"),
                "document_id": payload.get("document_id"),
                "version_id": payload.get("version_id"),
            })

        # Stage 5: Cross-encoder reranking
        reranked_results = self.reranker.rerank(
            query=query,
            candidates=candidate_results,
            top_k=limit,
        )

        return reranked_results
