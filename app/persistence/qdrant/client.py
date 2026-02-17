"""
Qdrant Client Initialization

Handles Qdrant client creation with connection pooling, retry logic,
and graceful error handling.
"""

import time
import logging
import atexit
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config.settings import QdrantSettings
from app.shared.errors import ApplicationError

logger = logging.getLogger(__name__)

# Infrastructure constants
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

# Global client instance (initialized once)
_client: Optional[QdrantClient] = None
_collection_name: Optional[str] = None
_vector_dimension: Optional[int] = None


class QdrantConnectionError(ApplicationError):
    """Qdrant connection failed after all retries"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=503, error_code="QDRANT_UNAVAILABLE", **kwargs)


class QdrantCollectionError(ApplicationError):
    """Qdrant collection operation failed"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=500, error_code="QDRANT_COLLECTION_ERROR", **kwargs)


def create_qdrant_client(config: QdrantSettings) -> QdrantClient:
    """
    Create Qdrant client with connection retry logic.
    
    Configuration:
    - Connection URL (host:port or cloud URL)
    - API key (for Qdrant Cloud)
    - Prefer gRPC (performance optimization)
    - Timeout configuration
    
    Args:
        config: QdrantSettings instance from app.config.settings
        
    Returns:
        QdrantClient instance
        
    Raises:
        QdrantConnectionError: If all connection retries fail
    """
    logger.info("Initializing Qdrant client...")
    
    # Attempt connection with retry logic
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Creating Qdrant client (attempt {attempt}/{MAX_RETRIES})"
            )
            
            # Build client configuration
            client_kwargs = {
                "url": config.qdrant_url,
                "timeout": config.qdrant_search_timeout,
                "prefer_grpc": config.qdrant_prefer_grpc,
            }
            
            # Add API key if provided (Qdrant Cloud)
            if config.qdrant_api_key:
                client_kwargs["api_key"] = config.qdrant_api_key
            
            client = QdrantClient(**client_kwargs)
            
            # Test connection: List collections
            collections = client.get_collections()
            
            logger.info(
                f"Qdrant client created successfully "
                f"(collections: {len(collections.collections)}, url: {config.qdrant_url})"
            )
            
            return client
            
        except Exception as e:
            if attempt < MAX_RETRIES:
                backoff_seconds = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Qdrant connection failed (attempt {attempt}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {backoff_seconds}s..."
                )
                time.sleep(backoff_seconds)
            else:
                logger.error(
                    f"Qdrant connection failed after {MAX_RETRIES} attempts: {e}"
                )
                raise QdrantConnectionError(
                    f"Qdrant unavailable after {MAX_RETRIES} attempts: {e}"
                )


def init_qdrant_client(config: QdrantSettings) -> QdrantClient:
    """
    Initialize the global Qdrant client.
    
    This function should be called once during application startup.
    Subsequent calls return the existing client instance.
    
    Args:
        config: QdrantSettings instance
        
    Returns:
        QdrantClient instance
        
    Raises:
        RuntimeError: If client already initialized
    """
    global _client, _collection_name, _vector_dimension
    
    if _client is not None:
        logger.warning("Qdrant client already initialized")
        return _client
    
    _client = create_qdrant_client(config)
    _collection_name = config.get_collection_name_with_env("dev")  # TODO: Get from AppSettings
    _vector_dimension = config.qdrant_embedding_dim
    
    logger.info(
        f"Qdrant client initialized "
        f"(collection: {_collection_name}, dimension: {_vector_dimension})"
    )
    
    return _client


def get_qdrant_client() -> QdrantClient:
    """
    Get the initialized Qdrant client.
    
    Returns:
        QdrantClient instance
        
    Raises:
        RuntimeError: If client not initialized
    """
    if _client is None:
        raise RuntimeError(
            "Qdrant client not initialized. Call init_qdrant_client() first."
        )
    return _client


def get_collection_name() -> str:
    """
    Get the configured collection name.
    
    Returns:
        Collection name string
        
    Raises:
        RuntimeError: If client not initialized
    """
    if _collection_name is None:
        raise RuntimeError(
            "Qdrant client not initialized. Call init_qdrant_client() first."
        )
    return _collection_name


def get_vector_dimension() -> int:
    """
    Get the configured vector dimension.
    
    Returns:
        Vector dimension (e.g., 768, 1536)
        
    Raises:
        RuntimeError: If client not initialized
    """
    if _vector_dimension is None:
        raise RuntimeError(
            "Qdrant client not initialized. Call init_qdrant_client() first."
        )
    return _vector_dimension


def cleanup_qdrant():
    """
    Cleanup Qdrant resources.
    
    Closes client connections gracefully.
    Called automatically at shutdown via atexit.
    """
    global _client, _collection_name, _vector_dimension
    
    if _client is None:
        return
    
    try:
        logger.info("Shutting down Qdrant client...")
        # Qdrant client doesn't have explicit close, but we clear the reference
        _client = None
        _collection_name = None
        _vector_dimension = None
        logger.info("Qdrant client shutdown complete")
    except Exception as e:
        logger.error(f"Error during Qdrant cleanup: {e}")


# Register cleanup on shutdown
atexit.register(cleanup_qdrant)
