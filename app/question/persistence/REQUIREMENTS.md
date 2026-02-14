# Question Persistence - Read-Only Repositories

## 1. Purpose

The **persistence** subdirectory handles:

- Read-only data access for questions, topics, coding problems
- Multi-tenant filtering (organization_id, scope enforcement)
- Hierarchical topic resolution (parent-child relationships)
- Query optimization (caching, batch queries, index usage)
- Repository pattern (abstraction over database queries)

**Critical responsibility:** Efficient, safe read access to question data with strict tenant isolation.

---

## 2. Responsibilities

### 2.1 Read-Only Enforcement

**Must enforce:**

- NO create operations (questions created via admin module)
- NO update operations (questions updated via admin module)
- NO delete operations (soft delete via admin module)
- Only SELECT queries allowed

**Why:**

- Separation of concerns (admin module owns question CRUD)
- Prevent accidental data modification during selection
- Clear audit trail (all mutations go through admin module)

---

### 2.2 Multi-Tenant Filtering

**Must enforce:**

- Questions with `scope = 'public'` → visible to all organizations
- Questions with `scope = 'organization'` → filtered by organization_id
- Questions with `scope = 'private'` → visible only to creator (admin user)
- Default filter: `(scope = 'public' OR (scope = 'organization' AND organization_id = :org_id))`

---

### 2.3 Repository Interfaces

**Three main repositories:**

1. **QuestionRepository:** Filter questions by difficulty, topic, organization
2. **TopicRepository:** Hierarchical topic filtering, parent-child resolution
3. **CodingProblemRepository:** Retrieve coding problems with test cases (excluding hidden outputs)

---

## 3. QuestionRepository

### 3.1 Interface

```python
class QuestionRepository(ABC):
    """
    Read-only repository for questions.

    All methods are SELECT only (no mutations).
    """

    @abstractmethod
    def get_by_id(self, question_id: int, organization_id: int) -> Optional[Question]:
        """
        Retrieve single question by ID.

        Enforces multi-tenant filtering (returns None if not accessible).
        """
        pass

    @abstractmethod
    def filter_by_criteria(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[list[int]] = None,
        question_type: Optional[str] = None,
        is_active: bool = True
    ) -> list[Question]:
        """
        Filter questions by criteria with multi-tenant enforcement.

        Returns: List of questions matching filters
        """
        pass

    @abstractmethod
    def get_random(
        self,
        organization_id: int,
        difficulty: str,
        topic_ids: list[int],
        exclude_ids: list[int] = []
    ) -> Optional[Question]:
        """
        Get random question matching criteria.

        Used for static pool selection when Qdrant unavailable.
        """
        pass

    @abstractmethod
    def get_by_ids_batch(
        self,
        question_ids: list[int],
        organization_id: int
    ) -> dict[int, Question]:
        """
        Batch retrieve questions by IDs.

        Returns: {question_id: Question} (missing IDs omitted)
        """
        pass
```

---

### 3.2 Implementation

```python
class SQLAlchemyQuestionRepository(QuestionRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_by_id(self, question_id: int, organization_id: int) -> Optional[Question]:
        """
        Retrieve question with multi-tenant check.
        """
        question = self.db.query(QuestionModel).filter(
            QuestionModel.id == question_id,
            QuestionModel.is_active == True,
            or_(
                QuestionModel.scope == 'public',
                and_(
                    QuestionModel.scope == 'organization',
                    QuestionModel.organization_id == organization_id
                )
            )
        ).first()

        return question

    def filter_by_criteria(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[list[int]] = None,
        question_type: Optional[str] = None,
        is_active: bool = True
    ) -> list[Question]:
        """
        Filter questions with multi-tenant enforcement.
        """
        query = self.db.query(QuestionModel).filter(
            QuestionModel.is_active == is_active,
            or_(
                QuestionModel.scope == 'public',
                and_(
                    QuestionModel.scope == 'organization',
                    QuestionModel.organization_id == organization_id
                )
            )
        )

        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)

        if topic_ids:
            query = query.filter(QuestionModel.topic_id.in_(topic_ids))

        if question_type:
            query = query.filter(QuestionModel.question_type == question_type)

        return query.all()

    def get_random(
        self,
        organization_id: int,
        difficulty: str,
        topic_ids: list[int],
        exclude_ids: list[int] = []
    ) -> Optional[Question]:
        """
        Get random question (fallback when Qdrant unavailable).
        """
        query = self.db.query(QuestionModel).filter(
            QuestionModel.difficulty == difficulty,
            QuestionModel.topic_id.in_(topic_ids),
            QuestionModel.is_active == True,
            or_(
                QuestionModel.scope == 'public',
                and_(
                    QuestionModel.scope == 'organization',
                    QuestionModel.organization_id == organization_id
                )
            )
        )

        if exclude_ids:
            query = query.filter(QuestionModel.id.notin_(exclude_ids))

        # PostgreSQL random
        return query.order_by(func.random()).first()

    def get_by_ids_batch(
        self,
        question_ids: list[int],
        organization_id: int
    ) -> dict[int, Question]:
        """
        Batch retrieve questions (single query).
        """
        questions = self.db.query(QuestionModel).filter(
            QuestionModel.id.in_(question_ids),
            QuestionModel.is_active == True,
            or_(
                QuestionModel.scope == 'public',
                and_(
                    QuestionModel.scope == 'organization',
                    QuestionModel.organization_id == organization_id
                )
            )
        ).all()

        return {q.id: q for q in questions}
```

---

## 4. TopicRepository

### 4.1 Hierarchical Topic Structure

**Table: topics**

```sql
CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_topic_id INTEGER REFERENCES topics(id),  -- NULL for root
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_topics_parent ON topics(parent_topic_id);
```

**Example hierarchy:**

```
Technical (root)
├── Algorithms
│   ├── Sorting
│   ├── Searching
│   └── Graph Traversal
├── Data Structures
│   ├── Arrays
│   ├── Trees
│   └── Hash Tables
└── System Design
    ├── Microservices
    └── Caching
```

---

### 4.2 Interface

```python
class TopicRepository(ABC):
    """
    Read-only repository for hierarchical topics.
    """

    @abstractmethod
    def get_by_id(self, topic_id: int) -> Optional[Topic]:
        """Get topic by ID."""
        pass

    @abstractmethod
    def get_descendants(self, topic_id: int) -> list[int]:
        """
        Get all descendant topic IDs (recursive).

        Example: topic_id=2 ("Algorithms") → [2, 5, 6, 7] (Algorithms + children)
        """
        pass

    @abstractmethod
    def get_ancestors(self, topic_id: int) -> list[int]:
        """
        Get all ancestor topic IDs (path to root).

        Example: topic_id=5 ("Sorting") → [5, 2, 1] (Sorting → Algorithms → Technical)
        """
        pass

    @abstractmethod
    def get_topic_tree(self, root_topic_id: Optional[int] = None) -> dict:
        """
        Get full topic tree as nested dict.

        Returns: {"id": 1, "name": "Technical", "children": [...]}
        """
        pass

    @abstractmethod
    def resolve_topic_path(self, topic_id: int) -> str:
        """
        Build breadcrumb path from root to topic.

        Example: topic_id=5 → "Technical > Algorithms > Sorting"
        """
        pass
```

---

### 4.3 Implementation

```python
class SQLAlchemyTopicRepository(TopicRepository):
    def __init__(self, db_session: Session, cache: Optional[Redis] = None):
        self.db = db_session
        self.cache = cache

    def get_by_id(self, topic_id: int) -> Optional[Topic]:
        """Get topic with caching."""
        if self.cache:
            cached = self.cache.get(f"topic:{topic_id}")
            if cached:
                return json.loads(cached)

        topic = self.db.query(TopicModel).filter(
            TopicModel.id == topic_id,
            TopicModel.is_active == True
        ).first()

        if topic and self.cache:
            self.cache.setex(f"topic:{topic_id}", 3600, json.dumps(topic.to_dict()))

        return topic

    def get_descendants(self, topic_id: int) -> list[int]:
        """
        Recursive CTE to get all descendants.
        """
        # Recursive CTE query
        cte = self.db.query(
            TopicModel.id,
            TopicModel.parent_topic_id
        ).filter(
            TopicModel.id == topic_id
        ).cte(name="topic_tree", recursive=True)

        cte_alias = aliased(cte, name="t")
        topic_alias = aliased(TopicModel, name="topics")

        recursive_part = self.db.query(
            topic_alias.id,
            topic_alias.parent_topic_id
        ).join(
            cte_alias,
            topic_alias.parent_topic_id == cte_alias.c.id
        )

        topic_tree = cte.union_all(recursive_part)

        results = self.db.query(topic_tree.c.id).all()

        return [r[0] for r in results]

    def get_ancestors(self, topic_id: int) -> list[int]:
        """
        Walk up parent chain to root.
        """
        ancestors = []
        current_id = topic_id

        while current_id:
            topic = self.get_by_id(current_id)
            if not topic:
                break

            ancestors.append(current_id)
            current_id = topic.parent_topic_id

        return ancestors

    def resolve_topic_path(self, topic_id: int) -> str:
        """
        Build breadcrumb path.
        """
        ancestors = self.get_ancestors(topic_id)
        ancestors.reverse()  # Root first

        names = []
        for ancestor_id in ancestors:
            topic = self.get_by_id(ancestor_id)
            if topic:
                names.append(topic.name)

        return " > ".join(names)
```

---

## 5. CodingProblemRepository

### 5.1 Security Requirement

**Critical:** Never expose hidden test case expected outputs to candidates

**Why:**

- Candidates could hardcode outputs
- Defeats the purpose of testing logic

**Solution:**

- Filter test cases by `is_hidden` flag
- Return `input` for all test cases
- Return `expected_output` only for visible test cases

---

### 5.2 Interface

```python
class CodingProblemRepository(ABC):
    """
    Read-only repository for coding problems.
    """

    @abstractmethod
    def get_by_id(self, problem_id: int, include_hidden: bool = False) -> Optional[CodingProblem]:
        """
        Get coding problem with test cases.

        Args:
            problem_id: Problem ID
            include_hidden: If False (default), excludes hidden test case expected outputs
        """
        pass

    @abstractmethod
    def filter_by_criteria(
        self,
        difficulty: Optional[str] = None,
        topic_ids: Optional[list[int]] = None,
        is_active: bool = True
    ) -> list[CodingProblem]:
        """
        Filter coding problems.
        """
        pass

    @abstractmethod
    def get_starter_code(self, problem_id: int, language: str) -> Optional[str]:
        """
        Get starter code template for language.

        Example: language='python' → returns Python function skeleton
        """
        pass
```

---

### 5.3 Implementation

```python
class SQLAlchemyCodingProblemRepository(CodingProblemRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_by_id(self, problem_id: int, include_hidden: bool = False) -> Optional[CodingProblem]:
        """
        Get coding problem with filtered test cases.
        """
        problem = self.db.query(CodingProblemModel).filter(
            CodingProblemModel.id == problem_id,
            CodingProblemModel.is_active == True
        ).first()

        if not problem:
            return None

        # Load test cases
        test_cases_query = self.db.query(CodingTestCaseModel).filter(
            CodingTestCaseModel.problem_id == problem_id
        )

        if not include_hidden:
            # Exclude hidden expected outputs (security)
            test_cases = []
            for tc in test_cases_query.all():
                test_case = tc.to_dict()

                if tc.is_hidden:
                    # Remove expected_output for hidden cases
                    test_case['expected_output'] = None

                test_cases.append(test_case)
        else:
            test_cases = [tc.to_dict() for tc in test_cases_query.all()]

        problem_dict = problem.to_dict()
        problem_dict['test_cases'] = test_cases

        return problem_dict

    def filter_by_criteria(
        self,
        difficulty: Optional[str] = None,
        topic_ids: Optional[list[int]] = None,
        is_active: bool = True
    ) -> list[CodingProblem]:
        """
        Filter coding problems.
        """
        query = self.db.query(CodingProblemModel).filter(
            CodingProblemModel.is_active == is_active
        )

        if difficulty:
            query = query.filter(CodingProblemModel.difficulty == difficulty)

        if topic_ids:
            # PostgreSQL array contains: ANY(topic_ids) IN (:filter_ids)
            query = query.filter(
                CodingProblemModel.topic_ids.overlap(topic_ids)
            )

        return query.all()

    def get_starter_code(self, problem_id: int, language: str) -> Optional[str]:
        """
        Get starter code for language.
        """
        problem = self.db.query(CodingProblemModel).filter(
            CodingProblemModel.id == problem_id
        ).first()

        if not problem or not problem.starter_code:
            return None

        # starter_code is JSONB: {"python": "def solution():", "javascript": "function solution() {}"}
        return problem.starter_code.get(language)
```

---

## 6. Query Optimization

### 6.1 Caching Strategy

**What to cache:**

- Topic hierarchy (changes infrequently, safe to cache for 1 hour)
- Public questions (changes infrequently, cache for 5 minutes)
- Coding problem metadata (cache for 1 hour)

**What NOT to cache:**

- Organization-specific questions (tenant-specific, risk of leakage)
- Active questions count (changes frequently)

**Implementation:**

```python
def get_with_cache(
    cache_key: str,
    fetch_fn: Callable,
    ttl_seconds: int = 3600
):
    """
    Generic cache-aside pattern.
    """
    # Check cache
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch from DB
    data = fetch_fn()

    # Store in cache
    if data:
        redis.setex(cache_key, ttl_seconds, json.dumps(data))

    return data
```

---

### 6.2 Batch Queries

**Problem:** N+1 query problem when loading related data

**Solution:** Batch load in single query

**Example:**

```python
# Bad: N+1 queries
questions = question_repo.filter_by_criteria(...)
for question in questions:
    topic = topic_repo.get_by_id(question.topic_id)  # N queries

# Good: Batch load
questions = question_repo.filter_by_criteria(...)
topic_ids = [q.topic_id for q in questions]
topics = topic_repo.get_by_ids_batch(topic_ids)  # 1 query
```

---

### 6.3 Index Usage

**Critical indexes:**

```sql
-- Questions
CREATE INDEX idx_questions_org_difficulty ON questions(organization_id, difficulty) WHERE is_active = TRUE;
CREATE INDEX idx_questions_topic_difficulty ON questions(topic_id, difficulty) WHERE is_active = TRUE;
CREATE INDEX idx_questions_scope_active ON questions(scope, is_active);

-- Topics
CREATE INDEX idx_topics_parent ON topics(parent_topic_id) WHERE is_active = TRUE;

-- Coding Problems
CREATE INDEX idx_coding_problems_difficulty ON coding_problems(difficulty) WHERE is_active = TRUE;
CREATE INDEX idx_coding_problems_topics ON coding_problems USING GIN(topic_ids);  -- Array index
```

**Validate with EXPLAIN:**

```python
# In tests
query = question_repo.filter_by_criteria(organization_id=1, difficulty='medium')
explain = db.execute(f"EXPLAIN ANALYZE {query}")
assert "Index Scan" in explain  # Not "Seq Scan"
```

---

## 7. Configuration

### 7.1 PersistenceConfig

```python
@dataclass
class PersistenceConfig:
    enable_query_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_read_only_enforcement: bool = True
    read_only_db_user: str = 'readonly_user'
    batch_query_size: int = 100
    enable_multi_tenant_filtering: bool = True
    log_slow_queries: bool = True
    slow_query_threshold_ms: int = 1000
```

---

## 8. Observability

### 8.1 Metrics

**Must expose:**

- `question_repository_queries_total` (counter with label: method) - Total queries
- `question_repository_query_duration_seconds` (histogram with label: method) - Query latency
- `question_repository_cache_hits_total` (counter) - Cache hits
- `question_repository_cache_misses_total` (counter) - Cache misses

---

### 8.2 Logging

**Must log (INFO level):**

- Query executed (method, filters, result_count)
- Cache hit (cache_key)
- Cache miss (cache_key, fetch_time_ms)

**Must log (WARN level):**

- Slow query detected (method, duration_ms, query)
- Cache unavailable (fallback to DB)

**Must log (ERROR level):**

- Database connection failed
- Query failed (method, error_message)

---

## 9. Testing Requirements

### 9.1 Repository Tests

**Test: Multi-tenant filtering enforced**

```python
def test_multi_tenant_filtering():
    # Given: Org 1 has private question
    org1_question = create_question(organization_id=1, scope='organization')

    # When: Org 2 queries
    questions = question_repo.filter_by_criteria(organization_id=2, difficulty='medium')

    # Then: Org 1's question not returned
    assert org1_question.id not in [q.id for q in questions]
```

**Test: Public questions visible to all**

```python
def test_public_questions_visible():
    public_question = create_question(scope='public')

    questions = question_repo.filter_by_criteria(organization_id=99, difficulty='medium')

    assert public_question.id in [q.id for q in questions]
```

---

### 9.2 Topic Hierarchy Tests

**Test: Get descendants returns all children**

```python
def test_get_descendants():
    # Technical > Algorithms > Sorting
    technical = create_topic(name="Technical", parent=None)  # id=1
    algorithms = create_topic(name="Algorithms", parent=technical)  # id=2
    sorting = create_topic(name="Sorting", parent=algorithms)  # id=3

    descendants = topic_repo.get_descendants(technical.id)

    assert set(descendants) == {technical.id, algorithms.id, sorting.id}
```

**Test: Topic path resolved correctly**

```python
def test_resolve_topic_path():
    # Technical > Algorithms > Sorting
    sorting_topic_id = 3

    path = topic_repo.resolve_topic_path(sorting_topic_id)

    assert path == "Technical > Algorithms > Sorting"
```

---

### 9.3 Coding Problem Tests

**Test: Hidden test case expected outputs excluded**

```python
def test_hidden_test_cases_excluded():
    problem = create_coding_problem()
    create_test_case(problem_id=problem.id, input="[1,2,3]", expected="6", is_hidden=False)
    create_test_case(problem_id=problem.id, input="[4,5,6]", expected="15", is_hidden=True)

    retrieved = coding_problem_repo.get_by_id(problem.id, include_hidden=False)

    assert retrieved['test_cases'][0]['expected_output'] == "6"  # Visible
    assert retrieved['test_cases'][1]['expected_output'] is None  # Hidden
```

---

## 10. Critical Risks

1. **Accidental writes:** Code bug calls `repository.update()` → data corrupted
2. **Cache staleness:** Admin updates question → cache not invalidated → users see old version
3. **Query performance:** Missing index on frequent filter → slow queries → timeout
4. **Cross-tenant leak:** organization_id filter forgotten → Org 2 sees Org 1 questions
5. **Hidden output exposed:** `include_hidden=True` used incorrectly → candidate sees expected outputs
6. **SQL injection:** User input in filter → malicious SQL (prevented by parameterized queries)

---

## 11. Acceptance Criteria

**Persistence module is complete when:**

✅ QuestionRepository implemented (filter by difficulty/topic/org, get random, batch get)
✅ TopicRepository implemented (hierarchical resolution, descendants, ancestors, path)
✅ CodingProblemRepository implemented (get with test cases, exclude hidden, starter code)
✅ Multi-tenant filtering enforced (organization_id, scope checks)
✅ Read-only enforcement working (no create/update/delete operations)
✅ Caching layer working (topic hierarchy, public questions)
✅ Batch queries working (N+1 avoided)
✅ Indexes validated (EXPLAIN ANALYZE shows index usage)
✅ Metrics exposed (query count, latency, cache hit rate)
✅ All tests passing (multi-tenant, hierarchy, hidden test cases)

---

**End of Question Persistence Requirements**
