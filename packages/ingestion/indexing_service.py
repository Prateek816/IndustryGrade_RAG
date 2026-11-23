
import uuid

from qdrant_client.models import PointStruct
from sqlalchemy.orm import Session

from packages.core.models import Chunk
from packages.core.repositories.chunk_repository import ChunkRepository
from packages.ingestion.chunking.chunker import StructureAwareChunker
from packages.ingestion.embedding.embedder import EmbeddingService
from packages.ingestion.parsing.schemas import ParsedDocument
from packages.ingestion.vector_store import QdrantVectorStore


class IndexingService:

    def __init__(
        self,
        db: Session,
        chunker: StructureAwareChunker | None = None,
        embedder: EmbeddingService | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        self.db = db
        self.chunker = chunker or StructureAwareChunker()
        self.embedder = embedder or EmbeddingService()
        self.vector_store = vector_store or QdrantVectorStore()
        self.chunk_repo = ChunkRepository(db)

    def index_document(
        self,
        *,
        document: ParsedDocument,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
    ):

        # 1. Generate parent and child chunks.
        result = self.chunker.chunk(
            document=document,
            version_id=version_id,
        )

        # 2. Convert chunk objects into database rows.
        rows = []

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

        # 3. Prepare child embedding inputs.
        embedding_texts = [
            f"{' > '.join(child.heading_path)}\n\n{child.content}"
            for child in result.children
        ]

        vectors = self.embedder.embed(embedding_texts)

        # 4. Persist all chunks in PostgreSQL.
        with self.db.begin():
            self.chunk_repo.upsert_many(rows)

        # 5. Prepare deterministic Qdrant points.
        points = []

        for child, vector in zip(result.children, vectors):
            points.append(
                PointStruct(
                    id=str(child.id),
                    vector=vector.tolist(),
                    payload={
                        "document_id": str(document_id),
                        "version_id": str(version_id),
                        "parent_id": str(child.parent_id),
                        "content": child.content,
                        "heading_path": child.heading_path,
                        "page_start": child.page_start,
                        "page_end": child.page_end,
                        "token_count": child.token_count,
                    },
                )
            )

        # 6. Upsert vectors into Qdrant.
        self.vector_store.upsert(points)

        return {
            "parent_count": len(result.parents),
            "child_count": len(result.children),
            "indexed_count": len(points),
            "version_id": version_id,
        }
