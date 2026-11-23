
import uuid

from sqlalchemy.orm import Session
from qdrant_client import models

from packages.core.repositories.chunk_repository import ChunkRepository
from packages.ingestion.chunking.chunker import StructureAwareChunker
from packages.ingestion.embedding.embedder import EmbeddingService
from packages.ingestion.embedding.sparse_embedder import (
    SparseEmbeddingService,
)
from packages.ingestion.parsing.schemas import ParsedDocument
from packages.ingestion.vector_store import QdrantVectorStore


class IndexingService:

    def __init__(
        self,
        db: Session,
        chunker: StructureAwareChunker | None = None,
        embedder: EmbeddingService | None = None,
        sparse_embedder: SparseEmbeddingService | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        self.db = db

        self.chunker = chunker or StructureAwareChunker()
        self.embedder = embedder or EmbeddingService()
        self.sparse_embedder = (
            sparse_embedder or SparseEmbeddingService()
        )

        self.vector_store = vector_store or QdrantVectorStore()
        self.chunk_repo = ChunkRepository(db)

    def index_document(
        self,
        *,
        document: ParsedDocument,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
    ):

        # --------------------------------------------------
        # 1. Generate parent and child chunks
        # --------------------------------------------------

        result = self.chunker.chunk(
            document=document,
            version_id=version_id,
        )

        # --------------------------------------------------
        # 2. Convert parent and child chunks into DB rows
        # --------------------------------------------------

        rows = []

        # Parent chunks
        for index, parent in enumerate(result.parents):

            rows.append({
                "id": parent.id,
                "document_id": document_id,
                "version_id": version_id,
                "parent_id": None,
                "chunk_type": "parent",
                "chunk_index": index,
                "content": parent.content,
                "token_count": len(
                    self.chunker.tokenizer.encode(parent.content)
                ),
                "page_start": parent.page_start,
                "page_end": parent.page_end,
                "heading_path": parent.heading_path,
                "source_element_ids": [],
            })

        # Child chunks
        for index, child in enumerate(result.children):

            rows.append({
                "id": child.id,
                "document_id": document_id,
                "version_id": version_id,
                "parent_id": child.parent_id,
                "chunk_type": "child",
                "chunk_index": index,
                "content": child.content,
                "token_count": child.token_count,
                "page_start": child.page_start,
                "page_end": child.page_end,
                "heading_path": child.heading_path,
                "source_element_ids": child.source_element_ids,
            })

        # --------------------------------------------------
        # 3. Generate embedding inputs (child chunks only)
        # --------------------------------------------------

        embedding_texts = [
            f"{' > '.join(child.heading_path)}\n\n{child.content}"
            for child in result.children
        ]

        # --------------------------------------------------
        # 4. Generate dense and sparse embeddings
        # --------------------------------------------------

        dense_vectors = []
        sparse_vectors = []

        if embedding_texts:

            dense_vectors = self.embedder.embed(
                embedding_texts
            )

            sparse_vectors = self.sparse_embedder.embed(
                embedding_texts
            )

            # Ensure embedding counts match child chunks
            if len(dense_vectors) != len(result.children):
                raise ValueError(
                    "Dense embedding count does not match "
                    "the number of child chunks."
                )

            if len(sparse_vectors) != len(result.children):
                raise ValueError(
                    "Sparse embedding count does not match "
                    "the number of child chunks."
                )

        # --------------------------------------------------
        # 5. Persist parent and child chunks in PostgreSQL
        # --------------------------------------------------

        if rows:
            with self.db.begin():
                self.chunk_repo.upsert_many(rows)

        # --------------------------------------------------
        # 6. Prepare hybrid Qdrant points
        # --------------------------------------------------

        points = []

        for child, dense, sparse in zip(
            result.children,
            dense_vectors,
            sparse_vectors,
        ):

            # Convert dense vector to Python list
            dense_values = dense.tolist()

            # Convert sparse vector indices and values
            sparse_indices = [
                int(index) for index in sparse.indices
            ]

            sparse_values = [
                float(value) for value in sparse.values
            ]

            sparse_vector = models.SparseVector(
                indices=sparse_indices,
                values=sparse_values,
            )

            points.append(
                models.PointStruct(
                    id=str(child.id),

                    vector={
                        "dense": dense_values,
                        "bm25": sparse_vector,
                    },

                    payload={
                        "document_id": str(document_id),
                        "version_id": str(version_id),
                        "parent_id": str(child.parent_id),
                        "chunk_type": "child",
                        "content": child.content,
                        "heading_path": child.heading_path,
                        "page_start": child.page_start,
                        "page_end": child.page_end,
                        "token_count": child.token_count,
                    },
                )
            )

        # --------------------------------------------------
        # 7. Upsert hybrid vectors into Qdrant
        # --------------------------------------------------

        if points:
            self.vector_store.upsert(points)

        # --------------------------------------------------
        # 8. Return indexing statistics
        # --------------------------------------------------

        return {
            "document_id": str(document_id),
            "version_id": str(version_id),

            "parent_count": len(result.parents),
            "child_count": len(result.children),

            "dense_embedding_count": len(dense_vectors),
            "sparse_embedding_count": len(sparse_vectors),

            "indexed_count": len(points),
            "status": "completed",
        }
