"""
Qdrant Vector Storage Operations

Pure vector storage primitives: store, search, update, delete.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
)

from .client import (
    get_qdrant_client,
    get_collection_name,
    get_vector_dimension,
    QdrantCollectionError,
)
from app.shared.errors import ValidationError

logger = logging.getLogger(__name__)


def validate_vector_dimension(vector: List[float]) -> None:
    """
    Validate vector dimension matches collection configuration.
    
    Args:
        vector: Embedding vector
        
    Raises:
        ValidationError: If dimension mismatch
    """
    expected_dim = get_vector_dimension()
    actual_dim = len(vector)
    
    if actual_dim != expected_dim:
        raise ValidationError(
            f"Vector dimension mismatch: expected {expected_dim}, got {actual_dim}"
        )


def store_embedding(
    vector: List[float],
    organization_id: int,
    source_type: str,
    source_id: int,
    model_name: str,
    model_version: str,
    difficulty: Optional[str] = None,
    topic_id: Optional[int] = None,
    scope: Optional[str] = None,
) -> str:
    """
    Store embedding vector with metadata.
    
    Args:
        vector: Embedding vector (dimension must match collection)
        organization_id: Tenant ID (REQUIRED for multi-tenant isolation)
        source_type: Source type ("question", "resume", "job_description")
        source_id: Source entity ID
        model_name: Model name ("all-mpnet-base-v2", "text-embedding-ada-002", etc.)
        model_version: Model version ("v2")
        difficulty: Question difficulty (optional)
        topic_id: Question topic ID (optional)
        scope: Scope ("public", "private", "organization")
        
    Returns:
        point_id: Unique Qdrant point identifier (UUID)
        
    Raises:
        ValidationError: If vector dimension mismatch
        QdrantCollectionError: If storage fails
    """
    # Validate dimension
    validate_vector_dimension(vector)
    
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    # Generate unique point ID
    point_id = str(uuid.uuid4())
    
    # Build payload (lightweight metadata for filtering)
    payload = {
        "organization_id": organization_id,
        "source_type": source_type,
        "source_id": source_id,
        "model_name": model_name,
        "model_version": model_version,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # Add optional fields
    if difficulty:
        payload["difficulty"] = difficulty
    if topic_id:
        payload["topic_id"] = topic_id
    if scope:
        payload["scope"] = scope
    
    try:
        # Create point
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )
        
        # Upsert (insert or update)
        client.upsert(
            collection_name=collection_name,
            points=[point]
        )
        
        logger.debug(
            f"Stored embedding: {source_type}:{source_id} "
            f"(point_id={point_id}, org={organization_id})"
        )
        
        return point_id
        
    except Exception as e:
        logger.error(f"Failed to store embedding: {e}")
        raise QdrantCollectionError(f"Embedding storage failed: {e}")


def store_embeddings_batch(
    embeddings: List[Dict[str, Any]],
    batch_size: int = 100
) -> List[str]:
    """
    Store multiple embeddings in batches.
    
    More efficient than individual inserts.
    
    Args:
        embeddings: List of embedding dictionaries with keys:
            - vector: List[float]
            - organization_id: int
            - source_type: str
            - source_id: int
            - model_name: str
            - model_version: str
            - difficulty: Optional[str]
            - topic_id: Optional[int]
            - scope: Optional[str]
        batch_size: Points per batch (default: 100)
        
    Returns:
        List of point_ids
        
    Raises:
        ValidationError: If any vector dimension mismatch
        QdrantCollectionError: If batch storage fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    point_ids = []
    
    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i:i + batch_size]
        points = []
        
        for emb in batch:
            # Validate dimension
            validate_vector_dimension(emb["vector"])
            
            # Generate point ID
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            
            # Build payload
            payload = {
                "organization_id": emb["organization_id"],
                "source_type": emb["source_type"],
                "source_id": emb["source_id"],
                "model_name": emb["model_name"],
                "model_version": emb["model_version"],
                "created_at": datetime.utcnow().isoformat(),
            }
            
            # Add optional fields
            if "difficulty" in emb:
                payload["difficulty"] = emb["difficulty"]
            if "topic_id" in emb:
                payload["topic_id"] = emb["topic_id"]
            if "scope" in emb:
                payload["scope"] = emb["scope"]
            
            # Create point
            points.append(
                PointStruct(
                    id=point_id,
                    vector=emb["vector"],
                    payload=payload
                )
            )
        
        try:
            # Upsert batch
            client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            logger.debug(f"Stored batch: {len(points)} embeddings")
            
        except Exception as e:
            logger.error(f"Failed to store batch: {e}")
            raise QdrantCollectionError(f"Batch storage failed: {e}")
    
    logger.info(f"Stored {len(point_ids)} embeddings in {len(range(0, len(embeddings), batch_size))} batches")
    return point_ids


def search_embeddings(
    query_vector: List[float],
    organization_id: int,
    top_k: int = 10,
    score_threshold: float = 0.7,
    source_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    topic_id: Optional[int] = None,
    scope: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for similar embeddings with multi-tenant isolation.
    
    Args:
        query_vector: Query embedding (dimension must match collection)
        organization_id: Tenant ID (REQUIRED - enforces data isolation)
        top_k: Number of results to return (default: 10)
        score_threshold: Minimum similarity score (0.0-1.0)
        source_type: Filter by source ("question", "resume", "job_description")
        difficulty: Filter by difficulty ("easy", "medium", "hard")
        topic_id: Filter by topic ID
        scope: Filter by scope ("public", "private", "organization")
        
    Returns:
        List of search results with metadata and scores
        
    Raises:
        ValidationError: If query vector dimension mismatch
        QdrantCollectionError: If search fails
    """
    # Validate dimension
    validate_vector_dimension(query_vector)
    
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    # Build filter conditions (ALWAYS include organization_id)
    must_conditions = [
        FieldCondition(
            key="organization_id",
            match=MatchValue(value=organization_id),
        )
    ]
    
    # Add optional filters
    if source_type:
        must_conditions.append(
            FieldCondition(
                key="source_type",
                match=MatchValue(value=source_type),
            )
        )
    
    if difficulty:
        must_conditions.append(
            FieldCondition(
                key="difficulty",
                match=MatchValue(value=difficulty),
            )
        )
    
    if topic_id:
        must_conditions.append(
            FieldCondition(
                key="topic_id",
                match=MatchValue(value=topic_id),
            )
        )
    
    if scope:
        must_conditions.append(
            FieldCondition(
                key="scope",
                match=MatchValue(value=scope),
            )
        )
    
    try:
        # Execute search with filters
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=top_k,
            score_threshold=score_threshold,
        )
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "point_id": result.id,
                "score": result.score,
                "organization_id": result.payload.get("organization_id"),
                "source_type": result.payload.get("source_type"),
                "source_id": result.payload.get("source_id"),
                "model_name": result.payload.get("model_name"),
                "model_version": result.payload.get("model_version"),
                "difficulty": result.payload.get("difficulty"),
                "topic_id": result.payload.get("topic_id"),
                "scope": result.payload.get("scope"),
                "created_at": result.payload.get("created_at"),
            })
        
        logger.debug(
            f"Search completed: {len(formatted_results)} results "
            f"(org={organization_id}, filters={len(must_conditions)})"
        )
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise QdrantCollectionError(f"Vector search failed: {e}")


def update_embedding_metadata(
    point_id: str,
    metadata_updates: Dict[str, Any]
) -> None:
    """
    Update metadata for existing embedding.
    
    Note: Vector itself cannot be updated, only metadata.
    
    Args:
        point_id: Qdrant point ID
        metadata_updates: Dictionary of fields to update
        
    Raises:
        QdrantCollectionError: If update fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    try:
        client.set_payload(
            collection_name=collection_name,
            payload=metadata_updates,
            points=[point_id]
        )
        
        logger.debug(f"Updated metadata for point: {point_id}")
        
    except Exception as e:
        logger.error(f"Failed to update metadata: {e}")
        raise QdrantCollectionError(f"Metadata update failed: {e}")


def delete_embedding(point_id: str) -> None:
    """
    Delete embedding by point_id.
    
    Args:
        point_id: Qdrant point ID
        
    Raises:
        QdrantCollectionError: If deletion fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=[point_id]
        )
        
        logger.debug(f"Deleted embedding: {point_id}")
        
    except Exception as e:
        logger.error(f"Failed to delete embedding: {e}")
        raise QdrantCollectionError(f"Embedding deletion failed: {e}")


def delete_embeddings_by_source(
    source_type: str,
    source_id: int,
    organization_id: int
) -> None:
    """
    Delete all embeddings for a specific source.
    
    Use case: Delete question embeddings when question is deleted.
    
    Args:
        source_type: Source type ("question", "resume", "job_description")
        source_id: Source entity ID
        organization_id: Tenant ID (for safety)
        
    Raises:
        QdrantCollectionError: If deletion fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    # Build filter for deletion (include organization_id for safety)
    delete_filter = Filter(
        must=[
            FieldCondition(
                key="organization_id",
                match=MatchValue(value=organization_id),
            ),
            FieldCondition(
                key="source_type",
                match=MatchValue(value=source_type),
            ),
            FieldCondition(
                key="source_id",
                match=MatchValue(value=source_id),
            ),
        ]
    )
    
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=delete_filter
        )
        
        logger.info(
            f"Deleted embeddings for {source_type}:{source_id} "
            f"(org={organization_id})"
        )
        
    except Exception as e:
        logger.error(f"Failed to delete embeddings by source: {e}")
        raise QdrantCollectionError(f"Bulk deletion failed: {e}")


def get_embedding_by_id(point_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve embedding metadata by point_id.
    
    Note: Does not return the vector itself (large payload).
    
    Args:
        point_id: Qdrant point ID
        
    Returns:
        Metadata dictionary or None if not found
        
    Raises:
        QdrantCollectionError: If retrieval fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    try:
        points = client.retrieve(
            collection_name=collection_name,
            ids=[point_id],
            with_payload=True,
            with_vectors=False  # Don't return large vectors
        )
        
        if not points:
            return None
        
        point = points[0]
        return {
            "point_id": point.id,
            "organization_id": point.payload.get("organization_id"),
            "source_type": point.payload.get("source_type"),
            "source_id": point.payload.get("source_id"),
            "model_name": point.payload.get("model_name"),
            "model_version": point.payload.get("model_version"),
            "difficulty": point.payload.get("difficulty"),
            "topic_id": point.payload.get("topic_id"),
            "scope": point.payload.get("scope"),
            "created_at": point.payload.get("created_at"),
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve embedding: {e}")
        raise QdrantCollectionError(f"Embedding retrieval failed: {e}")
