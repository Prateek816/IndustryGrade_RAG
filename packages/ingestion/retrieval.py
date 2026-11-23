
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.models import Chunk
from packages.ingestion.embedding.embedder import EmbeddingService
from packages.ingestion.vector_store import QdrantVectorStore


class RetrievalService:

    def __init__(self, db: Session):
        self.db = db
        self.embedder = EmbeddingService()
        self.vector_store = QdrantVectorStore()

    def search(
        self,
        query: str,
        limit: int = 5,
        document_id: UUID | None = None,
    ):

        query_vector = self.embedder.embed([query])[0]

        hits = self.vector_store.search(
            vector=query_vector.tolist(),
            limit=limit,
            document_id=str(document_id) if document_id else None,
        )

        parent_ids = {
            UUID(hit.payload["parent_id"])
            for hit in hits
            if hit.payload and hit.payload.get("parent_id")
        }

        parents = self.db.scalars(
            select(Chunk).where(Chunk.id.in_(parent_ids))
        ).all() if parent_ids else []

        parent_map = {
            parent.id: parent for parent in parents
        }

        results = []

        for hit in hits:
            payload = hit.payload or {}
            parent_id = UUID(payload["parent_id"])
            parent = parent_map.get(parent_id)

            results.append({
                "chunk_id": str(hit.id),
                "score": hit.score,
                "content": payload.get("content", ""),
                "parent_content": parent.content if parent else None,
                "heading_path": payload.get("heading_path", []),
                "page_start": payload.get("page_start"),
                "page_end": payload.get("page_end"),
                "document_id": payload.get("document_id"),
                "version_id": payload.get("version_id"),
            })

        return results
