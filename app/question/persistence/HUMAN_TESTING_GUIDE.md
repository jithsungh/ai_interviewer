# Question Persistence Module — Human Testing Guide

**Module:** `app/question/persistence`  
**Ticket:** DEV-49  
**Purpose:** Verify read-only repository queries, entity mapping, hidden test-case masking, and recursive topic resolution  
**Prerequisites:** Running PostgreSQL with schema applied, seeded question/topic/coding_problem data

---

## Prerequisites

### 1. Verify Database Schema

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate

# Verify core tables exist
psql "$DATABASE_URL" -c "\d questions"
psql "$DATABASE_URL" -c "\d topics"
psql "$DATABASE_URL" -c "\d coding_problems"
psql "$DATABASE_URL" -c "\d coding_test_cases"
psql "$DATABASE_URL" -c "\d question_topics"
psql "$DATABASE_URL" -c "\d coding_problem_topics"
```

### 2. Seed Minimal Test Data

If the database is empty, insert minimal rows for testing:

```sql
-- Insert an organization (if not already present)
INSERT INTO organizations (id, name) VALUES (1, 'TestOrg') ON CONFLICT DO NOTHING;

-- Insert topics with hierarchy
INSERT INTO topics (id, organization_id, name, parent_topic_id) VALUES
  (1, 1, 'Computer Science', NULL),
  (2, 1, 'Algorithms', 1),
  (3, 1, 'Sorting', 2)
ON CONFLICT DO NOTHING;

-- Insert a question
INSERT INTO questions (id, organization_id, question_text, question_type, difficulty, is_active)
VALUES (1, 1, 'Explain quicksort', 'technical', 'medium', true)
ON CONFLICT DO NOTHING;

-- Link question ↔ topic
INSERT INTO question_topics (question_id, topic_id) VALUES (1, 2)
ON CONFLICT DO NOTHING;

-- Insert a coding problem
INSERT INTO coding_problems (id, organization_id, title, description, difficulty, starter_code_json)
VALUES (1, 1, 'Two Sum', 'Given an array...', 'easy', '{"python": "def two_sum(nums, target):"}')
ON CONFLICT DO NOTHING;

-- Insert test cases (visible + hidden)
INSERT INTO coding_test_cases (id, coding_problem_id, input_data, expected_output, is_hidden)
VALUES
  (1, 1, '{"nums": [2,7], "target": 9}', '{"result": [0,1]}', false),
  (2, 1, '{"nums": [3,3], "target": 6}', '{"result": [0,1]}', true)
ON CONFLICT DO NOTHING;
```

### 3. Start Python Shell

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
python
```

---

## Test Scenarios

### Test 1: QuestionRepository — Basic Queries

**Objective:** Verify question retrieval, filtering, and multi-tenant isolation.

#### 1.1 Get Question by ID

```python
from app.bootstrap.dependencies import get_db_session
from app.question.persistence import QuestionRepository

session = next(get_db_session())
repo = QuestionRepository(session)

q = repo.get_by_id(1, organization_id=1)
print(f"ID: {q.id}, Text: {q.question_text}, Difficulty: {q.difficulty}")
print(f"Topic IDs: {q.topic_ids}")
```

**Expected:**
```
ID: 1, Text: Explain quicksort, Difficulty: medium
Topic IDs: [2]
```

#### 1.2 Multi-Tenant Isolation

```python
q = repo.get_by_id(1, organization_id=999)
print(f"Result: {q}")
```

**Expected:**
```
Result: None
```

#### 1.3 Filter by Criteria

```python
results = repo.filter_by_criteria(organization_id=1, difficulty="medium")
print(f"Count: {len(results)}")
for r in results:
    print(f"  {r.id}: {r.question_text}")
```

#### 1.4 Count Available

```python
count = repo.count_available(organization_id=1)
print(f"Available questions: {count}")
```

**Expected:** `>= 1`

#### 1.5 Random Question

```python
q = repo.get_random(organization_id=1)
print(f"Random: {q.id} - {q.question_text}")
```

#### 1.6 Batch Get

```python
qs = repo.get_by_ids_batch([1], organization_id=1)
print(f"Batch result: {len(qs)} questions")
```

---

### Test 2: TopicRepository — Recursive CTE

**Objective:** Verify topic tree resolution, ancestor/descendant queries.

#### 2.1 List Topics for Organization

```python
from app.question.persistence import TopicRepository

topic_repo = TopicRepository(session)
topics = topic_repo.list_by_organization(organization_id=1)
print(f"Topics: {len(topics)}")
for t in topics:
    print(f"  {t.id}: {t.name} (parent={t.parent_topic_id})")
```

**Expected:** 3 topics with hierarchy Computer Science → Algorithms → Sorting

#### 2.2 Get Topic Tree

```python
tree = topic_repo.get_topic_tree(organization_id=1)
print(f"Root topics: {len(tree)}")
for root in tree:
    print(f"  {root['topic'].name}")
    for child in root.get('children', []):
        print(f"    {child['topic'].name}")
```

#### 2.3 Get Descendants (Recursive CTE)

```python
descendants = topic_repo.get_descendants(topic_id=1, organization_id=1)
print(f"Descendants of 'Computer Science': {[d.name for d in descendants]}")
```

**Expected:** `['Algorithms', 'Sorting']`

#### 2.4 Get Ancestors (Breadcrumb Path)

```python
ancestors = topic_repo.get_ancestors(topic_id=3, organization_id=1)
print(f"Ancestors of 'Sorting': {[a.name for a in ancestors]}")
```

**Expected:** `['Computer Science', 'Algorithms']`

#### 2.5 Resolve Breadcrumb Path

```python
path = topic_repo.resolve_topic_path(topic_id=3, organization_id=1)
print(f"Path: {path}")
```

**Expected:** `Computer Science > Algorithms > Sorting`

---

### Test 3: CodingProblemRepository — Hidden Test Case Masking

**Objective:** Verify that hidden test case outputs are masked for candidates.

#### 3.1 Get Problem with Masked Hidden Cases (Default)

```python
from app.question.persistence import CodingProblemRepository

coding_repo = CodingProblemRepository(session)
problem = coding_repo.get_by_id(1, organization_id=1)
print(f"Title: {problem.title}")
for tc in problem.test_cases:
    print(f"  Case {tc.id}: hidden={tc.is_hidden}, output={tc.expected_output}")
```

**Expected:** Hidden test case (#2) has `expected_output = "[hidden]"`

#### 3.2 Get Problem with Unmasked Hidden Cases (Admin View)

```python
problem = coding_repo.get_by_id(1, organization_id=1, include_hidden_outputs=True)
for tc in problem.test_cases:
    print(f"  Case {tc.id}: hidden={tc.is_hidden}, output={tc.expected_output}")
```

**Expected:** Hidden test case (#2) shows actual expected output

#### 3.3 Get Starter Code

```python
starter = coding_repo.get_starter_code(problem_id=1, organization_id=1)
print(f"Starter code: {starter}")
```

**Expected:** `{"python": "def two_sum(nums, target):"}`

---

### Test 4: Mapper Functions

**Objective:** Verify ORM → Entity mapping correctness.

```python
from app.question.persistence.mappers import (
    question_model_to_entity,
    topic_model_to_entity,
    coding_test_case_model_to_entity,
    coding_problem_model_to_entity,
)
from app.admin.persistence.models import QuestionModel

# Fetch raw ORM model
from sqlalchemy import select
stmt = select(QuestionModel).where(QuestionModel.id == 1)
model = session.execute(stmt).scalar_one_or_none()
entity = question_model_to_entity(model)
print(f"Entity type: {type(entity).__name__}")
print(f"Frozen: id={entity.id}, text={entity.question_text}")
```

**Expected:** Returns a frozen `QuestionEntity` dataclass

---

### Test 5: Automated Tests

#### 5.1 Unit Tests (No DB Required)

```bash
cd /home/jithsungh/projects/ai_interviewer
.venv/bin/python -m pytest tests/unit/question/persistence/ -v --tb=short
```

**Expected:** All tests pass (entities, mappers, repositories)

#### 5.2 Integration Tests (DB Required)

```bash
.venv/bin/python -m pytest tests/integration/question/persistence/ -v --tb=short
```

**Expected:** Tests pass or skip (skipped tests indicate no seeded data)

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: app.question.persistence` | Virtual env not activated | `source .venv/bin/activate` |
| `get_by_id returns None` | Wrong `organization_id` | Double-check org ID in seed data |
| `Hidden test case output visible` | `include_hidden_outputs=True` passed | Omit parameter for candidate view |
| `get_descendants returns empty` | No child topics seeded | Insert topics with `parent_topic_id` |
| `RecursionError in CTE` | Circular parent references | Check `parent_topic_id` for cycles |

---

## Module File Inventory

| File | Purpose |
|------|---------|
| `__init__.py` | Public API exports |
| `entities.py` | Frozen dataclasses: QuestionEntity, TopicEntity, CodingTestCaseEntity, CodingProblemEntity |
| `models.py` | Supplementary ORM models: QuestionTopicModel, CodingTestCaseModel, CodingProblemTopicModel |
| `mappers.py` | ORM → Entity mappers with hidden output masking |
| `repositories.py` | Read-only repos: QuestionRepository, TopicRepository (recursive CTE), CodingProblemRepository |
