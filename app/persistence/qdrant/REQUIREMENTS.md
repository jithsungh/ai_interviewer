# Qdrant - Vector Database Integration

## 1. Purpose

The **Qdrant** layer provides:

- Qdrant client initialization and connection management
- Collection management (create, validate, schema enforcement)
- Embedding storage (vectors + metadata)
- Similarity search (query vector, filters, top_k results)
- Multi-tenant isolation (organization_id filtering)

**Critical responsibility:** This is **pure vector storage**. It must:

- Store and retrieve embeddings efficiently
- Support metadata filtering (organization, difficulty, topic)
- **Contain ZERO AI logic** (AI module generates embeddings)
- **Contain ZERO business logic** (domain modules interpret results)

**Architectural note:**

> **Qdrant stores vectors. It does NOT generate them.**
> AI module creates embeddings. Qdrant stores them.
> Domain modules interpret search results.

---

## 2. Responsibilities

### 2.1 Client Initialization

**Must create Qdrant client with:**

- Connection URL (host:port)
- API key (for Qdrant Cloud)
- gRPC or REST mode (gRPC recommended for performance)
- Timeout configuration
- Retry logic

**Example configuration:**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

def create_qdrant_client(config: QdrantConfig) -> QdrantClient:
    """
    Create Qdrant client with connection pooling.

    Configuration:
    - qdrant_url: Server URL (http://localhost:6333 or cloud URL)
    - qdrant_api_key: API key for authentication (cloud only)
    - prefer_grpc: Use gRPC instead of REST (default: True)
    - timeout: Request timeout (default: 10s)
    """
    client = QdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
        prefer_grpc=config.prefer_grpc,
        timeout=config.search_timeout
    )

    # Test connection
    try:
        collections = client.get_collections()
        logger.info(f"Qdrant connection established. Collections: {len(collections.collections)}")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        raise ConnectionError("Qdrant unavailable") from e

    return client
```

---

### 2.2 Collection Management

**Must support collection schema management:**

**Schema:**

- **Collection name:** Configurable per environment (dev/staging/prod)
- **Vector dimension:** Must match embedding model (default: 768 for self-hosted all-mpnet-base-v2)
  - Supported: 768 (all-mpnet-base-v2), 1536 (OpenAI ada-002), 3072 (OpenAI large)
- **Distance metric:** Cosine similarity (default) or Euclidean/Dot product
- **Payload schema:** Metadata fields (organization_id, source_type, difficulty, topic)

---

#### Collection Creation

```python
from qdrant_client.models import Distance, VectorParams, PointStruct

def create_collection_if_not_exists(
    client: QdrantClient,
    collection_name: str,
    vector_dimension: int,
    distance: Distance = Distance.COSINE
):
    """
    Create collection with schema if it doesn't exist.

    Args:
        collection_name: Collection name (e.g., "embeddings_prod")
        vector_dimension: Vector size (e.g., 1536 for OpenAI ada-002)
        distance: Distance metric (COSINE, EUCLID, DOT)
    """
    try:
        # Check if collection exists
        collections = client.get_collections()
        existing_names = [c.name for c in collections.collections]

        if collection_name in existing_names:
            logger.info(f"Collection '{collection_name}' already exists")

            # Validate vector dimension
            collection_info = client.get_collection(collection_name)
            actual_dim = collection_info.config.params.vectors.size

            if actual_dim != vector_dimension:
                raise ValueError(
                    f"Collection dimension mismatch: expected {vector_dimension}, got {actual_dim}"
                )
        else:
            # Create collection
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_dimension,
                    distance=distance
                )
            )
            logger.info(f"Created collection '{collection_name}' with dimension {vector_dimension}")

    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise
```

---

#### Collection Validation

```python
def validate_collection_schema(
    client: QdrantClient,
    collection_name: str,
    expected_dimension: int
):
    """
    Validate collection schema matches expected configuration.

    Raises:
        ValueError: If schema mismatch detected
    """
    collection_info = client.get_collection(collection_name)
    actual_dim = collection_info.config.params.vectors.size

    if actual_dim != expected_dimension:
        raise ValueError(
            f"Vector dimension mismatch: expected {expected_dimension}, got {actual_dim}"
        )

    logger.info(f"Collection schema validated: {collection_name} (dim={actual_dim})")
```

---

### 2.3 Embedding Storage

**Must support storing embeddings with metadata:**

**Metadata schema:**

```python
from enum import Enum

class SourceType(str, Enum):
    QUESTION = "question"
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description"

class EmbeddingMetadata(BaseModel):
    """Metadata stored with each embedding."""

    # Multi-tenant isolation
    organization_id: int

    # Source identification
    source_type: SourceType
    source_id: int  # question_id, resume_id, etc.

    # Model provenance
    model_id: str  # "all-mpnet-base-v2" (default), "text-embedding-ada-002", etc.
    model_version: str  # "v2"

    # Content metadata (question-specific)
    difficulty: Optional[str] = None  # "easy", "medium", "hard"
    topic_id: Optional[int] = None
    scope: Optional[str] = None  # "public", "private", "org"

    # Timestamps
    created_at: str  # ISO 8601
```

---

#### Store Single Embedding

```python
from qdrant_client.models import PointStruct
import uuid

def store_embedding(
    client: QdrantClient,
    collection_name: str,
    vector: list[float],
    metadata: EmbeddingMetadata
) -> str:
    """
    Store embedding with metadata.

    Args:
        vector: Embedding vector (dimension must match collection)
        metadata: Metadata for filtering and provenance

    Returns:
        point_id: Unique identifier for stored point
    """
    # Generate unique point ID
    point_id = str(uuid.uuid4())

    # Validate vector dimension
    if len(vector) != config.vector_dimension:
        raise ValueError(
            f"Vector dimension mismatch: expected {config.vector_dimension}, got {len(vector)}"
        )

    # Create point
    point = PointStruct(
        id=point_id,
        vector=vector,
        payload=metadata.model_dump()
    )

    # Upsert (insert or update)
    client.upsert(
        collection_name=collection_name,
        points=[point]
    )

    logger.debug(f"Stored embedding: {metadata.source_type}:{metadata.source_id}")
    return point_id
```

---

#### Store Batch Embeddings

```python
def store_embeddings_batch(
    client: QdrantClient,
    collection_name: str,
    embeddings: list[tuple[list[float], EmbeddingMetadata]],
    batch_size: int = 100
):
    """
    Store multiple embeddings in batches.

    More efficient than individual inserts.

    Args:
        embeddings: List of (vector, metadata) tuples
        batch_size: Points per batch (default: 100)
    """
    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i:i + batch_size]

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=metadata.model_dump()
            )
            for vector, metadata in batch
        ]

        client.upsert(
            collection_name=collection_name,
            points=points
        )

        logger.debug(f"Stored batch: {len(points)} embeddings")
```

---

### 2.4 Similarity Search

**Must support semantic search with filters:**

**Search parameters:**

- **query_vector:** Embedding to search for (from AI module)
- **filters:** Metadata constraints (organization_id, difficulty, topic)
- **top_k:** Number of results to return (default: 10)
- **score_threshold:** Minimum similarity score (optional)

---

#### Basic Search

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

def search_embeddings(
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    top_k: int = 10,
    score_threshold: float = 0.7
) -> list[dict]:
    """
    Search for similar embeddings.

    Args:
        query_vector: Query embedding (dimension must match collection)
        top_k: Number of results to return
        score_threshold: Minimum similarity score (0.0-1.0)

    Returns:
        List of search results with metadata and scores
    """
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold
    )

    return [
        {
            "point_id": result.id,
            "score": result.score,
            "source_type": result.payload.get("source_type"),
            "source_id": result.payload.get("source_id"),
            "metadata": result.payload
        }
        for result in results
    ]
```

---

#### Search with Filters

```python
def search_with_filters(
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    organization_id: int,
    source_type: Optional[SourceType] = None,
    difficulty: Optional[str] = None,
    topic_id: Optional[int] = None,
    scope: Optional[str] = None,
    top_k: int = 10
) -> list[dict]:
    """
    Search embeddings with metadata filters.

    Filters:
    - organization_id: Multi-tenant isolation (REQUIRED)
    - source_type: Filter by source (question, resume, job_description)
    - difficulty: Filter by difficulty (easy, medium, hard)
    - topic_id: Filter by topic
    - scope: Filter by scope (public, private, org)

    Returns:
        List of filtered search results
    """
    # Build filter conditions
    conditions = [
        FieldCondition(
            key="organization_id",
            match=MatchValue(value=organization_id)
        )
    ]

    if source_type:
        conditions.append(
            FieldCondition(
                key="source_type",
                match=MatchValue(value=source_type.value)
            )
        )

    if difficulty:
        conditions.append(
            FieldCondition(
                key="difficulty",
                match=MatchValue(value=difficulty)
            )
        )

    if topic_id:
        conditions.append(
            FieldCondition(
                key="topic_id",
                match=MatchValue(value=topic_id)
            )
        )

    if scope:
        conditions.append(
            FieldCondition(
                key="scope",
                match=MatchValue(value=scope)
            )
        )

    # Execute search with filters
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=Filter(must=conditions),
        limit=top_k
    )

    return [
        {
            "point_id": result.id,
            "score": result.score,
            "source_id": result.payload.get("source_id"),
            "metadata": result.payload
        }
        for result in results
    ]
```

---

### 2.5 Update & Delete Operations

**Must support updating and deleting embeddings:**

**Update embedding metadata:**

```python
def update_embedding_metadata(
    client: QdrantClient,
    collection_name: str,
    point_id: str,
    metadata_updates: dict
):
    """
    Update metadata for existing embedding.

    Note: Vector cannot be updated, only metadata.
    """
    client.set_payload(
        collection_name=collection_name,
        payload=metadata_updates,
        points=[point_id]
    )

    logger.debug(f"Updated metadata for point: {point_id}")
```

**Delete embedding:**

```python
def delete_embedding(
    client: QdrantClient,
    collection_name: str,
    point_id: str
):
    """
    Delete embedding by point_id.
    """
    client.delete(
        collection_name=collection_name,
        points_selector=[point_id]
    )

    logger.debug(f"Deleted point: {point_id}")
```

**Delete by filter (bulk delete):**

```python
def delete_embeddings_by_source(
    client: QdrantClient,
    collection_name: str,
    source_type: SourceType,
    source_id: int
):
    """
    Delete all embeddings for a specific source.

    Use case: Delete embeddings when question/resume deleted.
    """
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="source_type",
                    match=MatchValue(value=source_type.value)
                ),
                FieldCondition(
                    key="source_id",
                    match=MatchValue(value=source_id)
                )
            ]
        )
    )

    logger.info(f"Deleted embeddings for {source_type}:{source_id}")
```

---

### 2.6 Health Check

**Must implement Qdrant connectivity check:**

```python
import time
from typing import Dict, Any

def check_qdrant_health() -> Dict[str, Any]:
    """
    Check Qdrant connectivity and collection status.

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "latency_ms": float,
            "collections": list[str],
            "collection_info": dict,
            "error": str | None
        }
    """
    try:
        start = time.perf_counter()

        # List collections
        collections = client.get_collections()

        latency_ms = (time.perf_counter() - start) * 1000

        # Get collection info
        collection_info = client.get_collection(config.collection_name)

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "collections": [c.name for c in collections.collections],
            "collection_info": {
                "name": collection_info.config.name,
                "vector_dimension": collection_info.config.params.vectors.size,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count
            },
            "error": None
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "latency_ms": None,
            "collections": None,
            "collection_info": None,
            "error": str(e)
        }
```

---

## 3. Connection Retry Logic

**Must implement retry on connection failure:**

```python
def create_qdrant_client_with_retry(config: QdrantConfig, max_retries: int = 3):
    """
    Create Qdrant client with connection retry.

    Retries on connection failure with exponential backoff.
    """
    for attempt in range(max_retries):
        try:
            client = QdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key,
                prefer_grpc=config.prefer_grpc,
                timeout=config.search_timeout
            )

            # Test connection
            client.get_collections()

            logger.info("Qdrant connection established")
            return client

        except Exception as e:
            if attempt == max_retries - 1:
                logger.critical(f"Failed to connect to Qdrant after {max_retries} attempts")
                raise ConnectionError(f"Qdrant unavailable: {e}") from e

            sleep_time = 2 ** attempt
            logger.warning(f"Qdrant connection failed (attempt {attempt + 1}/{max_retries}), retrying in {sleep_time}s...")
            time.sleep(sleep_time)
```

---

## 4. Graceful Shutdown

**Must cleanup on shutdown:**

```python
import atexit

def cleanup_qdrant():
    """
    Close Qdrant client.

    Called on application shutdown.
    """
    logger.info("Cleaning up Qdrant client...")

    # Close client (if using gRPC)
    if hasattr(client, 'close'):
        client.close()

    logger.info("Qdrant cleanup complete")

atexit.register(cleanup_qdrant)
```

---

## 5. Error Handling

**Must handle:**

1. **Connection timeout** - Qdrant unreachable
   - Retry with backoff
   - Fail gracefully

2. **Collection not found** - Missing collection
   - Create collection (if auto-create enabled)
   - Raise error (if auto-create disabled)

3. **Dimension mismatch** - Vector size != collection dimension
   - Validate before insert
   - Raise ValueError with clear message

4. **Search timeout** - Query takes too long
   - Reduce top_k
   - Add score_threshold
   - Log warning

---

## 6. Testing Requirements

### 6.1 Unit Tests

1. **Client initialization:** Valid config → client created
2. **Collection creation:** Create collection → collection exists
3. **Dimension validation:** Mismatch → ValueError raised
4. **Store embedding:** Valid vector + metadata → stored successfully
5. **Search:** Query vector → returns top_k results
6. **Search with filters:** organization_id filter → only matching results
7. **Delete:** Delete by point_id → point removed

---

### 6.2 Integration Tests

1. **Store and search:** Store 1000 embeddings → search returns relevant results
2. **Multi-tenant isolation:** Store embeddings for org 1 & 2 → search org 1 returns only org 1
3. **Batch insert:** Store 10,000 embeddings in batches → all stored correctly
4. **Metadata filtering:** Search with difficulty filter → only matching difficulty returned

---

### 6.3 Performance Tests

1. **Search latency:** Search 1000 vectors → p95 latency < 100ms
2. **Batch insert throughput:** Insert 10,000 vectors → < 10 seconds
3. **Concurrent searches:** 100 concurrent searches → no timeouts

---

## 7. Configuration

```python
from pydantic import BaseModel, Field

class QdrantConfig(BaseModel):
    """Qdrant vector database configuration."""

    # Connection
    qdrant_url: str = Field(..., description="Qdrant server URL")
    qdrant_api_key: Optional[str] = Field(None, description="API key for cloud Qdrant")

    # Collection
    collection_name: str = Field("embeddings", description="Default collection name")
    vector_dimension: int = Field(1536, description="Embedding vector dimension")
    distance_metric: str = Field("cosine", description="Distance metric (cosine, euclid, dot)")

    # Search
    search_timeout: int = Field(10, ge=1, le=60, description="Search timeout (seconds)")
    default_top_k: int = Field(10, ge=1, le=100, description="Default top_k for searches")

    # Features
    prefer_grpc: bool = Field(True, description="Use gRPC instead of REST")
    auto_create_collection: bool = Field(True, description="Auto-create collection if missing")

    # Health check
    health_check_interval: int = Field(60, ge=10, le=300, description="Health check interval (seconds)")
```

---

## 8. Critical Risks

1. **Dimension mismatch:** Store 768-dim vector in 1536-dim collection → query fails
2. **No organization_id filter:** Multi-tenant data leakage
3. **No vector validation:** Store invalid vector → collection corrupted
4. **Large batch insert:** Insert 1M vectors at once → memory exhaustion
5. **Search without filters:** Search all organizations → slow, data leakage
6. **AI logic in persistence:** Embedding generation in Qdrant module → boundary violation

---

## 9. Observability

### 9.1 Metrics

**Must expose:**

- `qdrant_embeddings_stored_total` (counter) - Total embeddings stored
- `qdrant_search_requests_total` (counter) - Total search requests
- `qdrant_search_duration_seconds` (histogram) - Search latency
- `qdrant_collection_points_count` (gauge) - Points in collection

---

### 9.2 Logging

**Must log:**

- Collection created (INFO)
- Embedding stored (DEBUG with source_type:source_id)
- Search performed (DEBUG with filters, top_k, result count)
- Dimension mismatch (ERROR with expected/actual)
- Connection failure (ERROR with retry count)

**Must NOT log:**

- Full vectors (high volume, not useful)
- Sensitive metadata (PII, if any)

---

## 10. Acceptance Criteria

**Qdrant module is complete when:**

✅ Qdrant client initialized with connection pooling
✅ Collection created with correct schema
✅ Vector dimension validation enforced
✅ Embedding storage with metadata working
✅ Similarity search with filters working
✅ Multi-tenant isolation enforced (organization_id filter)
✅ Batch insert efficient (100+ vectors/second)
✅ Connection retry with exponential backoff
✅ Health check returns status and collection info
✅ Graceful shutdown cleanup
✅ No AI logic in module (embeddings generated elsewhere)
✅ No business logic in module (results interpreted elsewhere)
✅ All tests passing

---

**End of Qdrant Requirements**
