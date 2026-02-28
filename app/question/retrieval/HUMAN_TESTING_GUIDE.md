# HUMAN TESTING GUIDE — question/retrieval

**Module:** `app/question/retrieval`
**Branch:** `feature/DEV-36-implement-maodule-question-retreival`
**Ticket:** DEV-36

---

## Prerequisites

| Dependency | Required | How to check |
|---|---|---|
| Python 3.12+ | Yes | `python3 --version` |
| Qdrant | Yes (primary) | `curl http://localhost:6333/health` |
| Redis | Yes (caching) | `redis-cli ping` → `PONG` |
| PostgreSQL | Yes (fallback) | `pg_isready -h localhost` |
| Virtualenv | Yes | `.venv/bin/python -c "import app"` |

### Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/ai_interviewer"
export QDRANT_URL="http://localhost:6333"
export QDRANT_API_KEY=""                  # Optional
export REDIS_URL="redis://localhost:6379/0"
export TESTING=1
```

---

## 1. Unit Tests (No Infrastructure Required)

```bash
# Run all retrieval unit tests
.venv/bin/python -m pytest tests/unit/question/retrieval/ -v

# Run individual test files
.venv/bin/python -m pytest tests/unit/question/retrieval/test_similarity.py -v
.venv/bin/python -m pytest tests/unit/question/retrieval/test_circuit_breaker.py -v
.venv/bin/python -m pytest tests/unit/question/retrieval/test_contracts.py -v
.venv/bin/python -m pytest tests/unit/question/retrieval/test_service.py -v
```

**Expected:** 105 tests, all PASSED.

| Test File | Tests | What it validates |
|---|---|---|
| `test_similarity.py` | 19 | Cosine similarity, normalization, repetition detection |
| `test_circuit_breaker.py` | 18 | State machine: CLOSED→OPEN→HALF_OPEN→CLOSED, thread safety |
| `test_contracts.py` | 23 | Pydantic validation, enums, default values, constraints |
| `test_service.py` | 45 | Cache hits, fallback, circuit breaker integration, hybrid search |

---

## 2. Integration Tests (Requires Running Infrastructure)

```bash
# Qdrant repository tests
.venv/bin/python -m pytest tests/integration/question/retrieval/test_qdrant_repository.py -v

# Redis cache tests
.venv/bin/python -m pytest tests/integration/question/retrieval/test_cache_repository.py -v

# PostgreSQL fallback tests
.venv/bin/python -m pytest tests/integration/question/retrieval/test_question_read_repository.py -v

# Full end-to-end service tests
.venv/bin/python -m pytest tests/integration/question/retrieval/test_retrieval_service.py -v
```

**Expected:** Tests pass when infrastructure is running; skipped when not.

---

## 3. Manual Testing via Python REPL

### 3.1 — Semantic Search (Happy Path)

```python
from app.question.retrieval.contracts import SearchCriteria
from app.question.retrieval.service import QdrantRetrievalService

svc = QdrantRetrievalService()
criteria = SearchCriteria(
    organization_id=1,
    query_vector=[0.1] * 768,  # Replace with actual embedding
    top_k=5,
    score_threshold=0.3,
)

result = svc.search_semantic(criteria)
print(f"Strategy: {result.strategy_used}")
print(f"Found: {result.total_found}")
print(f"Duration: {result.search_duration_ms:.1f}ms")
print(f"Cache hit: {result.cache_hit}")
for c in result.candidates:
    print(f"  Q{c.question_id}: score={c.similarity_score:.3f}")
```

**Verify:**
- `strategy_used` = `semantic`
- `fallback_activated` = `False`
- Candidates sorted by descending score
- All candidates have `similarity_score >= 0.3`

---

### 3.2 — Cache Verification

```python
# Run the same search again
result2 = svc.search_semantic(criteria)
print(f"Cache hit: {result2.cache_hit}")  # Should be True
```

**Verify:** `cache_hit = True` on second call with same parameters.

---

### 3.3 — Repetition Detection

```python
from app.question.retrieval.service import QdrantRetrievalService

svc = QdrantRetrievalService()

candidate_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
exchange_history = [
    {"question_id": 1, "question_embedding": [0.1, 0.2, 0.3, 0.4, 0.5]},  # Identical!
    {"question_id": 2, "question_embedding": [0.9, 0.8, 0.7, 0.6, 0.5]},  # Different
]

result = svc.check_repetition(candidate_embedding, exchange_history, threshold=0.85)
print(f"Acceptable: {result.is_acceptable}")      # False (identical found)
print(f"Max similarity: {result.max_similarity}")  # ≈ 1.0
print(f"Most similar: Q{result.most_similar_question_id}")  # 1
```

**Verify:**
- `is_acceptable = False` because candidate is identical to question 1
- `max_similarity ≈ 1.0`
- `most_similar_question_id = 1`

---

### 3.4 — Circuit Breaker Fallback

```python
from app.question.retrieval.service import QdrantRetrievalService

# Simulate circuit breaker open (do NOT do this in production)
for _ in range(5):
    QdrantRetrievalService._circuit_breaker.record_failure()

print(f"State: {svc.circuit_breaker_state}")  # "open"

criteria = SearchCriteria(
    organization_id=1,
    query_vector=[0.1] * 768,
    top_k=5,
)

# This will use PostgreSQL fallback
result = svc.search_semantic(criteria)
print(f"Strategy: {result.strategy_used}")       # static_fallback
print(f"Fallback: {result.fallback_activated}")   # True
print(f"Reason: {result.fallback_reason}")        # circuit_breaker_open

# Reset
QdrantRetrievalService.reset_circuit_breaker()
print(f"State after reset: {svc.circuit_breaker_state}")  # "closed"
```

---

### 3.5 — Hybrid Search

```python
from app.question.retrieval.contracts import HybridSearchWeights, SearchCriteria
from app.question.retrieval.service import QdrantRetrievalService

svc = QdrantRetrievalService()

resume_vec = [0.1] * 768   # Replace with actual resume embedding
jd_vec = [0.2] * 768       # Replace with actual JD embedding
weights = HybridSearchWeights(resume_weight=0.7, jd_weight=0.3)

criteria = SearchCriteria(
    organization_id=1,
    top_k=5,
    score_threshold=0.3,
)

result = svc.search_hybrid(resume_vec, jd_vec, criteria, weights)
print(f"Strategy: {result.strategy_used}")  # hybrid
```

---

## 4. Failure Scenarios to Test

| Scenario | How to trigger | Expected behavior |
|---|---|---|
| Qdrant down | Stop Qdrant container | Circuit breaker opens → PostgreSQL fallback |
| Redis down | Stop Redis container | Cache misses (non-fatal), searches still work |
| PostgreSQL down (fallback) | Stop DB | Fallback returns empty result, error logged |
| Empty results | Search with very high `score_threshold=0.99` | `total_found = 0`, `is_empty = True` |
| Dimension mismatch | Pass 256-dim vector to 768-dim collection | `ValueError` from Qdrant repo |
| Invalid org_id | Use `organization_id=0` | Pydantic validation error |

---

## 5. Multi-Tenant Isolation Check

```python
# Create questions for two different orgs
# Verify org A cannot see org B's private questions

criteria_org_a = SearchCriteria(
    organization_id=1,
    query_vector=[0.1] * 768,
    top_k=20,
    score_threshold=0.0,
    include_public=False,  # Only org's own questions
)

criteria_org_b = SearchCriteria(
    organization_id=2,
    query_vector=[0.1] * 768,
    top_k=20,
    score_threshold=0.0,
    include_public=False,
)

result_a = svc.search_semantic(criteria_org_a)
result_b = svc.search_semantic(criteria_org_b)

# Verify no overlap (assuming orgs have distinct questions)
ids_a = {c.question_id for c in result_a.candidates}
ids_b = {c.question_id for c in result_b.candidates}
print(f"Org A questions: {ids_a}")
print(f"Org B questions: {ids_b}")
print(f"Overlap: {ids_a & ids_b}")  # Should be empty
```

---

## 6. Architecture Checklist

- [ ] **No schema changes** — Uses existing `questions` table (admin module)
- [ ] **No cross-module domain imports** — Only reads admin's ORM model
- [ ] **Multi-tenant isolation** — Every query filters by `organization_id`
- [ ] **Circuit breaker** — Opens after 5 failures, half-opens after 60s
- [ ] **Cache** — TTL 1 hour, fallback results NOT cached
- [ ] **Fallback** — PostgreSQL random selection, relaxes difficulty if empty
- [ ] **Pure domain** — `similarity.py` has zero I/O dependencies
- [ ] **Thread-safe** — Circuit breaker uses `threading.Lock`
