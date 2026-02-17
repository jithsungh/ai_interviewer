"""
Qdrant Persistence Layer

Pure infrastructure module for vector database connectivity.
Provides Qdrant client, collection management, and vector operations.

⚠️ CONTAINS ZERO BUSINESS LOGIC ⚠️
⚠️ CONTAINS ZERO AI LOGIC ⚠️

Public API:
- init_qdrant(): Initialize client and create collection
- store_embedding(): Store single embedding
- store_embeddings_batch(): Store multiple embeddings
- search_embeddings(): Semantic search with filters
- delete_embedding(): Delete single embedding
- delete_embeddings_by_source(): Bulk delete by source
- check_qdrant_health(): Health check
- cleanup_qdrant(): Graceful shutdown
"""

from .client import (
    init_qdrant_client,
    get_qdrant_client,
    get_collection_name,
    get_vector_dimension,
    cleanup_qdrant,
    QdrantConnectionError,
    QdrantCollectionError,
)
from .collections import (
    create_collection_if_not_exists,
    validate_collection_schema,
    delete_collection,
    get_collection_info,
)
from .operations import (
    validate_vector_dimension,
    store_embedding,
    store_embeddings_batch,
    search_embeddings,
    update_embedding_metadata,
    delete_embedding,
    delete_embeddings_by_source,
    get_embedding_by_id,
)
from .health import (
    check_qdrant_health,
    check_qdrant_connectivity,
    check_collection_health,
    get_health_check_endpoint_response,
    log_qdrant_stats,
    HealthStatus,
)

__all__ = [
    # Client management
    "init_qdrant_client",
    "get_qdrant_client",
    "get_collection_name",
    "get_vector_dimension",
    "cleanup_qdrant",
    
    # Exceptions
    "QdrantConnectionError",
    "QdrantCollectionError",
    
    # Collection management
    "create_collection_if_not_exists",
    "validate_collection_schema",
    "delete_collection",
    "get_collection_info",
    
    # Vector operations
    "validate_vector_dimension",
    "store_embedding",
    "store_embeddings_batch",
    "search_embeddings",
    "update_embedding_metadata",
    "delete_embedding",
    "delete_embeddings_by_source",
    "get_embedding_by_id",
    
    # Health checks
    "check_qdrant_health",
    "check_qdrant_connectivity",
    "check_collection_health",
    "get_health_check_endpoint_response",
    "log_qdrant_stats",
    "HealthStatus",
    
    # Convenience initialization
    "init_qdrant",
]


def init_qdrant(config):
    """
    Initialize Qdrant infrastructure.
    
    Call this once during application startup.
    Sets up client connection and creates collection if needed.
    
    Args:
        config: QdrantSettings instance from app.config.settings
        
    Example:
        from app.persistence.qdrant import init_qdrant
        from app.config.settings import QdrantSettings
        
        # At application startup
        qdrant_settings = QdrantSettings()
        init_qdrant(qdrant_settings)
    """
    # Initialize client
    init_qdrant_client(config)
    
    # Create collection if not exists
    create_collection_if_not_exists()
    
    # Log health
    log_qdrant_stats()
