
from sqlalchemy import select
from qdrant_client import models

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from packages.core.database import SessionLocal
from packages.core.models import Chunk

from packages.ingestion.embedding.embedder import EmbeddingService
from packages.ingestion.embedding.sparse_embedder import (
    SparseEmbeddingService,
)
from packages.ingestion.vector_store import QdrantVectorStore


BATCH_SIZE = 64


def main():

    dense_model = EmbeddingService()
    sparse_model = SparseEmbeddingService()
    vector_store = QdrantVectorStore()

    total = 0

    with SessionLocal() as db:

        query = (
            select(Chunk)
            .where(Chunk.chunk_type == "child")
            .order_by(Chunk.created_at)
        )

        chunks = db.scalars(query).yield_per(BATCH_SIZE)

        batch = []

        def index_batch(items):

            texts = [
                f"{' > '.join(chunk.heading_path)}\n\n{chunk.content}"
                for chunk in items
            ]

            dense_vectors = dense_model.embed(texts)
            sparse_vectors = sparse_model.embed(texts)

            points = []

            for chunk, dense, sparse in zip(
                items,
                dense_vectors,
                sparse_vectors,
            ):
                points.append(
                    models.PointStruct(
                        id=str(chunk.id),

                        vector={
                            "dense": dense.tolist(),
                            "bm25": models.SparseVector(
                                indices=sparse.indices,
                                values=sparse.values,
                            ),
                        },

                        payload={
                            "document_id": str(chunk.document_id),
                            "version_id": str(chunk.version_id),
                            "parent_id": str(chunk.parent_id),
                            "content": chunk.content,
                            "heading_path": chunk.heading_path,
                            "page_start": chunk.page_start,
                            "page_end": chunk.page_end,
                            "token_count": chunk.token_count,
                        },
                    )
                )

            vector_store.upsert(points)

        for chunk in chunks:
            batch.append(chunk)

            if len(batch) >= BATCH_SIZE:
                index_batch(batch)
                total += len(batch)
                print(f"Indexed {total} chunks")
                batch = []

        if batch:
            index_batch(batch)
            total += len(batch)

    print(f"\nHybrid reindex complete: {total} child chunks")


if __name__ == "__main__":
    main()
