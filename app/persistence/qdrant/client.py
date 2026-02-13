"""
Qdrant Vector Database Client

Semantic search and embeddings storage (DR-2, FR-4.5).
"""

from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
from app.config import settings


class QdrantVectorStore:
    """
    Qdrant client wrapper for vector operations.
    
    Supports semantic question retrieval to prevent repetition (FR-4.5).
    """
    
    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self.collection_name = "interview_questions"
    
    def connect(self):
        """Initialize Qdrant client"""
        if settings.qdrant_api_key:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
                prefer_grpc=True,
                grpc_port=settings.qdrant_grpc_port,
            )
        else:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
    
    def disconnect(self):
        """Close Qdrant connection"""
        if self.client:
            self.client.close()
    
    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1536,  # OpenAI embeddings default
        distance: Distance = Distance.COSINE
    ):
        """Create a new collection"""
        if not self.client:
            raise RuntimeError("Qdrant client not connected")
        
        self.client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )
    
    async def upsert_points(
        self,
        collection_name: str,
        points: List[PointStruct]
    ):
        """Insert or update points"""
        if not self.client:
            raise RuntimeError("Qdrant client not connected")
        
        self.client.upsert(
            collection_name=collection_name,
            points=points
        )
    
    async def search_similar(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filter_conditions: Optional[Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Used to find semantically similar questions (FR-4.5).
        """
        if not self.client:
            raise RuntimeError("Qdrant client not connected")
        
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=filter_conditions,
            limit=limit,
            score_threshold=score_threshold,
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload
            }
            for result in results
        ]
    
    async def delete_points(
        self,
        collection_name: str,
        point_ids: List[int]
    ):
        """Delete points by IDs"""
        if not self.client:
            raise RuntimeError("Qdrant client not connected")
        
        self.client.delete(
            collection_name=collection_name,
            points_selector=point_ids
        )


# Global Qdrant client instance
qdrant_client = QdrantVectorStore()


def get_qdrant() -> QdrantVectorStore:
    """
    Dependency for FastAPI routes.
    
    Usage:
        @router.get("/similar-questions")
        async def search(qdrant: QdrantVectorStore = Depends(get_qdrant)):
            ...
    """
    return qdrant_client
