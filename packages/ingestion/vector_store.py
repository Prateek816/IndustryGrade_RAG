
import os

from qdrant_client import QdrantClient, models


class QdrantVectorStore:

    def __init__(self):
        self.collection_name = os.getenv(
            "QDRANT_COLLECTION",
            "rag_chunks",
        )

        self.dimension = int(
            os.getenv("EMBEDDING_DIMENSION", "384")
        )

        self.client = QdrantClient(
            url=os.getenv(
                "QDRANT_URL",
                "http://localhost:6333",
            ),
        )

        self.ensure_collection()

    def ensure_collection(self):

        if self.client.collection_exists(self.collection_name):
            info = self.client.get_collection(self.collection_name)

            if info.config.params.vectors.size != self.dimension:
                raise ValueError(
                    "Qdrant collection dimension mismatch. "
                    "Use a new collection or recreate the existing one."
                )

            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dimension,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert(
        self,
        points: list[models.PointStruct],
    ):

        if not points:
            return

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        vector: list[float],
        limit: int = 5,
        document_id: str | None = None,
    ):

        query_filter = None

        if document_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(
                            value=document_id
                        ),
                    )
                ]
            )

        return self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        ).points
