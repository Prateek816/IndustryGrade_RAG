
import os

from qdrant_client import QdrantClient, models


class QdrantVectorStore:

    def __init__(self):
        self.collection_name = os.getenv(
            "QDRANT_COLLECTION",
            "rag_chunks_hybrid",
        )

        self.dimension = int(
            os.getenv("EMBEDDING_DIMENSION", "384")
        )

        self.client = QdrantClient(
            url=os.getenv(
                "QDRANT_URL",
                "http://localhost:6333",
            )
        )

        self.ensure_collection()

    def ensure_collection(self):

        if not self.client.collection_exists(
            self.collection_name
        ):
            self.client.create_collection(
                collection_name=self.collection_name,

                vectors_config={
                    "dense": models.VectorParams(
                        size=self.dimension,
                        distance=models.Distance.COSINE,
                    )
                },

                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )

        # Create payload indexes for frequently used filters.
        for field in ["document_id", "version_id"]:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    def upsert(self, points: list[models.PointStruct]):

        if not points:
            return

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def hybrid_search(
        self,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
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

        sparse_query = models.SparseVector(
            indices=sparse_indices,
            values=sparse_values,
        )

        results = self.client.query_points(
            collection_name=self.collection_name,

            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=max(limit * 4, 20),
                ),
                models.Prefetch(
                    query=sparse_query,
                    using="bm25",
                    limit=max(limit * 4, 20),
                ),
            ],

            query=models.RrfQuery(
                rrf=models.Rrf()
            ),

            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        return results.points
