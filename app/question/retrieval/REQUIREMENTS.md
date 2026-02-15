# Question Retrieval - Qdrant Semantic Search

## 1. Purpose

The **retrieval** subdirectory handles:

- Semantic similarity search using Qdrant vector database
- Resume-based question personalization
- Job description-based relevance ranking
- Multi-tenant collection isolation
- Metadata filtering (difficulty, topic, scope)
- Similarity scoring for repetition prevention

**Critical responsibility:** Efficient, relevant question retrieval using embeddings with strict tenant isolation.

---

## 2. Responsibilities

### 2.1 Embedding-Based Retrieval

**Provides:**

- Search questions by vector similarity
- Combine resume embedding + JD embedding for hybrid search
- Rank results by relevance score
- Filter by metadata (difficulty, topic, organization)

**Must:**

- Use Qdrant client from persistence module
- Enforce organization_id filter (multi-tenant isolation)
- Return question IDs with similarity scores
- Handle Qdrant unavailability gracefully (fallback to static pool)

---

### 2.2 Similarity Scoring

**Provides:**

- Cosine similarity computation between question embeddings
- Used for repetition detection
- Threshold-based filtering

**Formula:**

```
similarity(A, B) = (A · B) / (||A|| × ||B||)
```

**Range:** [-1, 1], higher = more similar

---

### 2.3 Multi-Tenant Isolation

**Must enforce:**

- Questions with `scope = 'public'` → visible to all (organization_id filter not applied)
- Questions with `scope = 'organization'` → filtered by organization_id
- Qdrant filter must include organization_id for non-public questions

**Qdrant filter example:**

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

filter = Filter(
    must=[
        FieldCondition(
            key="organization_id",
            match=MatchValue(value=organization_id)
        ),
        FieldCondition(
            key="difficulty",
            match=MatchValue(value="medium")
        )
    ]
)
```

---

## 3. Qdrant Collection Schema

### 3.1 Collection: questions_embeddings

**Vector configuration:**

- `vector_dimension`: 1536 (OpenAI text-embedding-ada-002)
- `distance`: Cosine

**Payload schema:**

```python
{
    "question_id": 12345,              # PostgreSQL question.id
    "organization_id": 42,             # Tenant ID
    "question_type": "behavioral",     # behavioral, technical, coding
    "difficulty": "medium",            # easy, medium, hard
    "topic_id": 7,                     # PostgreSQL topic.id
    "topic_name": "communication",     # Denormalized for filtering
    "scope": "organization",           # public, organization, private
    "is_active": true,                 # Soft delete flag
    "created_at": "2026-02-14T10:00:00Z",
    "indexed_at": "2026-02-14T10:05:00Z"
}
```

**Indexes:**

- Payload indexes on: organization_id, difficulty, topic_id, scope, is_active

---

## 4. Retrieval Strategies

### 4.1 Resume-Based Personalization

**Use case:** Behavioral questions tailored to candidate's experience

**Algorithm:**

1. Generate resume embedding (done by AI module, stored in embeddings table)
2. Retrieve resume embedding vector
3. Search questions collection with resume vector as query
4. Filter by: organization_id, question_type=behavioral, difficulty
5. Return top-k results

**Example:**

```python
def retrieve_personalized_questions(
    organization_id: int,
    resume_embedding_id: int,
    difficulty: str,
    top_k: int = 10
) -> list[QuestionCandidate]:
    """
    Retrieve questions personalized to candidate's resume.
    """
    # Get resume embedding vector
    resume_embedding = embeddings_repo.get_by_id(resume_embedding_id)

    if not resume_embedding:
        raise ValueError("Resume embedding not found")

    # Build filter
    filter = Filter(
        must=[
            FieldCondition(key="organization_id", match=MatchValue(value=organization_id)),
            FieldCondition(key="question_type", match=MatchValue(value="behavioral")),
            FieldCondition(key="difficulty", match=MatchValue(value=difficulty)),
            FieldCondition(key="is_active", match=MatchValue(value=True))
        ]
    )

    # Search
    results = qdrant_client.search(
        collection_name="questions_embeddings",
        query_vector=resume_embedding.vector,
        query_filter=filter,
        limit=top_k
    )

    return [
        QuestionCandidate(
            question_id=hit.payload["question_id"],
            similarity_score=hit.score,
            metadata=hit.payload
        )
        for hit in results
    ]
```

---

### 4.2 Job Description-Based Relevance

**Use case:** Technical questions aligned with job requirements

**Algorithm:**

1. Generate JD embedding (done by AI module)
2. Retrieve JD embedding vector
3. Search questions with JD vector as query
4. Filter by: organization_id, question_type=technical, difficulty, topics
5. Return top-k results

**Hybrid approach (combine resume + JD):**

```python
def retrieve_hybrid_questions(
    organization_id: int,
    resume_embedding_id: int,
    jd_embedding_id: int,
    difficulty: str,
    top_k: int = 10,
    resume_weight: float = 0.5,
    jd_weight: float = 0.5
) -> list[QuestionCandidate]:
    """
    Retrieve questions using weighted combination of resume + JD embeddings.
    """
    resume_vec = get_embedding_vector(resume_embedding_id)
    jd_vec = get_embedding_vector(jd_embedding_id)

    # Weighted average
    hybrid_vec = [
        resume_weight * r + jd_weight * j
        for r, j in zip(resume_vec, jd_vec)
    ]

    # Normalize
    hybrid_vec = normalize_vector(hybrid_vec)

    # Search with hybrid vector
    filter = build_filter(organization_id, difficulty, ...)
    results = qdrant_client.search(
        collection_name="questions_embeddings",
        query_vector=hybrid_vec,
        query_filter=filter,
        limit=top_k
    )

    return parse_results(results)
```

---

### 4.3 Topic-Based Filtering

**Use case:** Questions constrained to specific topics (e.g., "microservices", "data structures")

**Algorithm:**

1. Query with generic embedding or no embedding (retrieve by filter only)
2. Filter by: organization_id, topic_id IN (topic_ids), difficulty
3. Return random or top-rated questions

**Implementation:**

```python
def retrieve_by_topic(
    organization_id: int,
    topic_ids: list[int],
    difficulty: str,
    top_k: int = 10
) -> list[QuestionCandidate]:
    """
    Retrieve questions filtered by topic.

    Uses scroll API (no vector query) for exact filter match.
    """
    filter = Filter(
        must=[
            FieldCondition(key="organization_id", match=MatchValue(value=organization_id)),
            FieldCondition(key="topic_id", match=MatchValue(any=topic_ids)),
            FieldCondition(key="difficulty", match=MatchValue(value=difficulty)),
            FieldCondition(key="is_active", match=MatchValue(value=True))
        ]
    )

    # Use scroll for filter-only queries
    results, _ = qdrant_client.scroll(
        collection_name="questions_embeddings",
        scroll_filter=filter,
        limit=top_k
    )

    return parse_results(results)
```

---

## 5. Repetition Detection

### 5.1 Similarity Computation

**Purpose:** Detect if candidate question is too similar to previously asked questions

**Algorithm:**

```python
def compute_similarity_to_history(
    candidate_question_id: int,
    candidate_embedding: list[float],
    exchange_history: list[dict]
) -> dict[int, float]:
    """
    Compute similarity between candidate and all previous questions.

    Returns: {previous_question_id: similarity_score}
    """
    similarities = {}

    for exchange in exchange_history:
        if not exchange.get('question_embedding'):
            continue

        previous_embedding = exchange['question_embedding']
        similarity = cosine_similarity(candidate_embedding, previous_embedding)

        similarities[exchange['question_id']] = similarity

    return similarities
```

---

### 5.2 Threshold-Based Filtering

**Thresholds:**

- `identical_threshold = 0.95`: Essentially the same question (reject)
- `similar_threshold = 0.85`: Too similar for good candidate experience (reject)
- `acceptable_threshold < 0.85`: Different enough (accept)

**Decision logic:**

```python
def is_acceptable_candidate(
    candidate_question_id: int,
    candidate_embedding: list[float],
    exchange_history: list[dict],
    threshold: float = 0.85
) -> tuple[bool, float]:
    """
    Check if candidate is acceptable (not too similar to history).

    Returns: (is_acceptable, max_similarity)
    """
    similarities = compute_similarity_to_history(
        candidate_question_id,
        candidate_embedding,
        exchange_history
    )

    if not similarities:
        return (True, 0.0)  # No history, always acceptable

    max_similarity = max(similarities.values())

    return (max_similarity < threshold, max_similarity)
```

---

## 6. Fallback Strategies

### 6.1 Qdrant Unavailable

**Scenario:** Qdrant connection timeout or error

**Fallback:**

1. Log warning
2. Fall back to PostgreSQL static pool (no semantic search)
3. Random selection from filtered pool
4. Return to semantic search when Qdrant recovers

**Circuit breaker pattern:**

```python
class QdrantRetrievalService:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_duration=60  # 60 seconds
        )

    def search(self, ...):
        if self.circuit_breaker.is_open():
            logger.warning("Qdrant circuit breaker open, using static fallback")
            return fallback_to_static_pool(...)

        try:
            results = qdrant_client.search(...)
            self.circuit_breaker.record_success()
            return results
        except QdrantException as e:
            logger.error(f"Qdrant search failed: {e}")
            self.circuit_breaker.record_failure()
            return fallback_to_static_pool(...)
```

---

### 6.2 No Results Found

**Scenario:** Search returns 0 results

**Fallback hierarchy:**

1. Relax difficulty filter (medium → [easy, medium, hard])
2. Relax topic filter (remove topic constraint)
3. Broaden organization scope (add public questions)
4. Fallback to static pool
5. Trigger LLM generation (last resort)

---

## 7. Embedding Management

### 7.1 Question Embedding Creation

**Note:** Embedding creation is NOT in retrieval module (done by AI module or admin module)

**Retrieval module only reads embeddings.**

**Expected workflow:**

1. Admin creates/imports question → question stored in PostgreSQL
2. Background job generates embedding → stored in embeddings table + Qdrant
3. Retrieval module searches Qdrant → returns question_id
4. Selection module fetches full question from PostgreSQL

---

### 7.2 Embedding Synchronization

**Challenge:** Keep Qdrant in sync with PostgreSQL

**Strategy:**

- PostgreSQL is source of truth
- Qdrant is search index (can rebuild if lost)
- Background sync job reconciles daily
- Immediately index new questions (event-driven)

**Sync job:**

```python
def sync_questions_to_qdrant():
    """
    Daily job to sync questions from PostgreSQL to Qdrant.

    Ensures Qdrant index is up-to-date.
    """
    # Get all active questions without embeddings in Qdrant
    unindexed_questions = db.query(Question).filter(
        Question.is_active == True,
        Question.id.notin_(get_indexed_question_ids())
    ).all()

    for question in unindexed_questions:
        # Generate embedding if not exists
        if not question.embedding:
            embedding = generate_embedding(question.question_text)
            store_embedding(question.id, embedding)

        # Index in Qdrant
        index_question_in_qdrant(question)

    logger.info(f"Synced {len(unindexed_questions)} questions to Qdrant")
```

---

## 8. Performance Optimization

### 8.1 Search Optimization

**Qdrant configuration:**

- HNSW indexing for fast approximate nearest neighbor search
- `ef` parameter tuning (trade-off: speed vs accuracy)
- Payload indexes on frequently filtered fields

**Example:**

```python
# Create collection with optimized settings
qdrant_client.create_collection(
    collection_name="questions_embeddings",
    vectors_config={
        "size": 1536,
        "distance": "Cosine"
    },
    hnsw_config={
        "m": 16,  # Number of connections per element
        "ef_construct": 100,  # Size of dynamic candidate list
    },
    optimizers_config={
        "indexing_threshold": 10000  # Start indexing after 10k vectors
    }
)

# Create payload indexes
qdrant_client.create_payload_index(
    collection_name="questions_embeddings",
    field_name="organization_id",
    field_schema="integer"
)
```

**Search tuning:**

```python
# Adjust ef parameter for search
results = qdrant_client.search(
    collection_name="questions_embeddings",
    query_vector=vector,
    query_filter=filter,
    limit=10,
    search_params={"hnsw_ef": 128}  # Higher = more accurate but slower
)
```

---

### 8.2 Caching

**Strategy:** Cache search results for repeated queries

**Key:** `hash(organization_id, difficulty, topic_ids, embedding_id)`
**TTL:** 1 hour (questions don't change frequently)

**Implementation:**

```python
def search_with_cache(
    organization_id: int,
    resume_embedding_id: int,
    difficulty: str,
    topic_ids: list[int],
    top_k: int = 10
) -> list[QuestionCandidate]:
    """
    Search with Redis cache layer.
    """
    cache_key = f"question_search:{organization_id}:{resume_embedding_id}:{difficulty}:{':'.join(map(str, sorted(topic_ids)))}"

    # Check cache
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Perform search
    results = qdrant_search(...)

    # Cache results
    redis.setex(cache_key, 3600, json.dumps(results))

    return results
```

---

## 9. Observability

### 9.1 Metrics

**Must expose:**

- `question_retrieval_total` (counter with labels: strategy, success) - Total retrievals
- `question_retrieval_duration_seconds` (histogram with label: strategy) - Search latency
- `question_retrieval_results_count` (histogram) - Result count distribution
- `question_repetition_similarity_score` (histogram) - Similarity score distribution
- `qdrant_circuit_breaker_open` (gauge) - Circuit breaker state

---

### 9.2 Logging

**Must log (INFO level):**

- Search initiated (organization_id, difficulty, topic_ids, embedding_id)
- Search completed (result_count, max_similarity, duration_ms)
- Cache hit/miss
- Fallback activated (reason, fallback_strategy)

**Must log (WARN level):**

- Qdrant timeout (fallback to static pool)
- No results found (will trigger fallback)
- Circuit breaker opened

**Must log (ERROR level):**

- Qdrant connection failed (retrying)
- Embedding not found (expected embedding_id missing)

---

## 10. Testing Requirements

### 10.1 Retrieval Tests

**Test: Resume-based search returns relevant questions**

```python
def test_resume_based_retrieval():
    # Given: Resume embedding for "Python developer with 5 years experience"
    resume_embedding_id = create_resume_embedding("Python developer...")

    # When: Search for behavioral questions
    results = retrieve_personalized_questions(
        organization_id=1,
        resume_embedding_id=resume_embedding_id,
        difficulty="medium",
        top_k=5
    )

    # Then: Results should be relevant to Python development
    assert len(results) >= 3
    assert all(r.metadata["question_type"] == "behavioral" for r in results)
    assert any("team" in r.metadata["topic_name"] for r in results)
```

**Test: Multi-tenant isolation enforced**

```python
def test_multi_tenant_isolation():
    # Given: Org 1 has question "What is your management style?"
    org1_question = create_question(organization_id=1, scope="organization")
    index_in_qdrant(org1_question)

    # When: Org 2 searches
    results = retrieve_by_topic(
        organization_id=2,
        topic_ids=[org1_question.topic_id],
        difficulty="medium"
    )

    # Then: Org 1's private question not returned
    assert org1_question.id not in [r.question_id for r in results]
```

**Test: Public questions visible to all**

```python
def test_public_questions_visible():
    # Given: Public question
    public_question = create_question(organization_id=999, scope="public")
    index_in_qdrant(public_question)

    # When: Org 1 searches
    results = retrieve_by_topic(
        organization_id=1,
        topic_ids=[public_question.topic_id],
        difficulty="medium"
    )

    # Then: Public question visible
    assert public_question.id in [r.question_id for r in results]
```

---

### 10.2 Similarity Tests

**Test: Identical embedding rejected**

```python
def test_similarity_identical():
    embedding = [0.1, 0.2, 0.3, ...]
    exchange_history = [{"question_id": 42, "question_embedding": embedding}]

    is_acceptable, similarity = is_acceptable_candidate(
        candidate_question_id=999,
        candidate_embedding=embedding,
        exchange_history=exchange_history,
        threshold=0.85
    )

    assert is_acceptable == False
    assert similarity >= 0.99  # Nearly identical
```

**Test: Similar embedding rejected**

```python
def test_similarity_too_similar():
    candidate_embedding = [0.1, 0.2, 0.3, ...]
    previous_embedding = [0.11, 0.19, 0.31, ...]  # Very similar
    exchange_history = [{"question_id": 42, "question_embedding": previous_embedding}]

    is_acceptable, similarity = is_acceptable_candidate(
        candidate_question_id=999,
        candidate_embedding=candidate_embedding,
        exchange_history=exchange_history,
        threshold=0.85
    )

    assert is_acceptable == False
    assert 0.85 <= similarity < 0.99
```

---

### 10.3 Fallback Tests

**Test: Qdrant unavailable → fallback to static**

```python
def test_qdrant_unavailable_fallback():
    # Given: Qdrant down
    with mock_qdrant_unavailable():
        # When: Search attempted
        results = retrieve_personalized_questions(
            organization_id=1,
            resume_embedding_id=123,
            difficulty="medium"
        )

        # Then: Fallback to static pool activated
        assert results  # Some results returned
        assert "fallback" in get_last_log_entry()
```

---

## 11. Critical Risks

1. **Cross-tenant leak:** organization_id filter missing → Org 1 sees Org 2 questions → data breach
2. **Embedding dimension mismatch:** Store 768-dim in 1536-dim collection → query fails
3. **Stale index:** PostgreSQL updated, Qdrant not synced → outdated questions returned
4. **Similarity false negatives:** Threshold too high → repetition not detected → candidate fatigued
5. **Qdrant exhaustion:** No circuit breaker → all requests timeout → system unresponsive

---

## 12. Acceptance Criteria

**Retrieval module is complete when:**

✅ Resume-based retrieval working (semantic search)
✅ JD-based retrieval working
✅ Hybrid search working (weighted resume + JD)
✅ Topic-based filtering working
✅ Multi-tenant isolation enforced (organization_id filter)
✅ Repetition detection via similarity scoring
✅ Qdrant fallback to static pool on failure
✅ Circuit breaker implemented
✅ Embedding sync job working
✅ Caching layer implemented (Redis)
✅ Metrics exposed (retrieval rate, latency, results count)
✅ All tests passing (retrieval, similarity, fallback, tenant isolation)

---

**End of Question Retrieval Requirements**
