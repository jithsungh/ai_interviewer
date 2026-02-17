"""
Qdrant Collection Management

Handles collection creation, validation, and schema enforcement.
"""

import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, CollectionStatus
from qdrant_client.http.exceptions import UnexpectedResponse

from .client import (
    get_qdrant_client,
    get_collection_name,
    get_vector_dimension,
    QdrantCollectionError,
)

logger = logging.getLogger(__name__)


def create_collection_if_not_exists(
    distance: Distance = Distance.COSINE
) -> None:
    """
    Create Qdrant collection with schema if it doesn't exist.
    
    Collection schema:
    - Vector dimension: From config (default: 768)
    - Distance metric: Cosine similarity (default)
    - Payload schema: Lightweight metadata for filtering
    
    Args:
        distance: Distance metric (COSINE, EUCLID, DOT)
        
    Raises:
        QdrantCollectionError: If collection creation fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    vector_dim = get_vector_dimension()
    
    try:
        # Check if collection already exists
        collections = client.get_collections()
        existing_names = [c.name for c in collections.collections]
        
        if collection_name in existing_names:
            logger.info(f"Collection '{collection_name}' already exists")
            # Validate schema
            validate_collection_schema()
            return
        
        # Create collection
        logger.info(
            f"Creating collection '{collection_name}' "
            f"(dimension={vector_dim}, distance={distance.value})"
        )
        
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_dim,
                distance=distance
            )
        )
        
        logger.info(f"Collection '{collection_name}' created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create collection '{collection_name}': {e}")
        raise QdrantCollectionError(
            f"Collection creation failed: {e}"
        )


def validate_collection_schema() -> None:
    """
    Validate collection schema matches expected configuration.
    
    Checks:
    - Collection exists
    - Vector dimension matches config
    - Collection is ready (not being deleted/created)
    
    Raises:
        ValueError: If schema mismatch detected
        QdrantCollectionError: If validation fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    expected_dim = get_vector_dimension()
    
    try:
        collection_info = client.get_collection(collection_name)
        
        # Check dimension
        actual_dim = collection_info.config.params.vectors.size
        if actual_dim != expected_dim:
            raise ValueError(
                f"Collection dimension mismatch: "
                f"expected {expected_dim}, got {actual_dim}. "
                f"Delete collection or update config."
            )
        
        # Check status
        if collection_info.status != CollectionStatus.GREEN:
            logger.warning(
                f"Collection '{collection_name}' status: {collection_info.status}"
            )
        
        logger.info(
            f"Collection schema validated: {collection_name} "
            f"(dimension={actual_dim}, points={collection_info.points_count})"
        )
        
    except UnexpectedResponse as e:
        if e.status_code == 404:
            raise QdrantCollectionError(
                f"Collection '{collection_name}' not found. "
                f"Call create_collection_if_not_exists() first."
            )
        raise QdrantCollectionError(f"Collection validation failed: {e}")
    
    except Exception as e:
        logger.error(f"Collection validation error: {e}")
        raise


def delete_collection() -> None:
    """
    Delete the configured collection.
    
    ⚠️ DANGEROUS: Deletes all vectors in the collection.
    Use only for testing or cleanup.
    
    Raises:
        QdrantCollectionError: If deletion fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    try:
        logger.warning(f"Deleting collection '{collection_name}'...")
        client.delete_collection(collection_name)
        logger.info(f"Collection '{collection_name}' deleted")
        
    except Exception as e:
        logger.error(f"Failed to delete collection '{collection_name}': {e}")
        raise QdrantCollectionError(f"Collection deletion failed: {e}")


def get_collection_info() -> dict:
    """
    Get collection information (stats, schema).
    
    Returns:
        Dictionary with collection metadata
        
    Raises:
        QdrantCollectionError: If retrieval fails
    """
    client = get_qdrant_client()
    collection_name = get_collection_name()
    
    try:
        collection_info = client.get_collection(collection_name)
        
        return {
            "name": collection_name,
            "points_count": collection_info.points_count,
            "vectors_count": collection_info.vectors_count or 0,
            "segments_count": collection_info.segments_count,
            "status": collection_info.status.value,
            "optimizer_status": collection_info.optimizer_status.ok,
            "vector_dimension": collection_info.config.params.vectors.size,
            "distance_metric": collection_info.config.params.vectors.distance.value,
        }
        
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        raise QdrantCollectionError(f"Collection info retrieval failed: {e}")
