# Admin Persistence — Human Testing Guide

## Quick Start

```bash
cd /home/jithsungh/projects/ai_interviewer

# Run all admin persistence unit tests (99 tests)
.venv/bin/python -m pytest tests/unit/admin/persistence/ -v

# Run full admin suite (domain + persistence = 207 tests)
.venv/bin/python -m pytest tests/unit/admin/ -v

# Compile-verify imports
.venv/bin/python -c "from app.admin.persistence import *; print('OK')"
```

## What to Verify

### 1. Mapper Round-Trips (test_mappers.py — 38 tests)

| Test Class | Count | Validates |
|---|---|---|
| `TestTemplateMapper` | 6 | model ↔ entity, scope enum conversion, null template_structure |
| `TestTemplateRoleMapper` | 1 | composite PK mapping |
| `TestTemplateRubricMapper` | 3 | section_name, round-trip |
| `TestRubricMapper` | 3 | scope enum, update preserves model identity |
| `TestDimensionMapper` | 3 | Decimal conversion, criteria JSONB |
| `TestRoleMapper` | 2 | scope enum, org_id nullable |
| `TestTopicMapper` | 2 | parent_topic_id, scope |
| `TestCodingTopicMapper` | 2 | topic_type enum, display_order |
| `TestQuestionMapper` | 3 | difficulty enum, question_type enum, round-trip |
| `TestCodingProblemMapper` | 2 | all JSONB array fields, source metadata |
| `TestWindowMapper` | 2 | InterviewScope enum, timezone string |
| `TestWindowMappingMapper` | 2 | selection_weight |
| `TestOverrideMapper` | 5 | all ContentTypes, unknown type raises, null fields |

### 2. Repository Logic (test_repositories.py — 61 tests)

| Test Class | Count | Validates |
|---|---|---|
| `TestSqlTemplateRepository` | 14 | CRUD, pagination, version, exists, role/rubric mappings |
| `TestSqlRubricRepository` | 4 | get, not-found, dimension set/get |
| `TestSqlRoleRepository` | 3 | get, count, exists |
| `TestSqlTopicRepository` | 4 | topic & coding_topic get, ancestor walk (chain & no-parent) |
| `TestSqlQuestionRepository` | 2 | get, type filter |
| `TestSqlCodingProblemRepository` | 1 | get with all fields |
| `TestSqlWindowRepository` | 3 | get, overlap subquery, set_mappings |
| `TestSqlSubmissionRepository` | 4 | template/role/window in-use checks |
| `TestSqlOverrideRepository` | 10 | CRUD, delete T/F, mark_stale, all ContentTypes, unknown |
| `TestSqlAuditLogRepository` | 3 | insert-only, no flush, optional fields |
| `TestPagination` | 4 | page 1/3/0/-5 offset calculation |

### 3. Migration SQL

Run the migration against a local PostgreSQL instance:

```bash
psql -U jithsungh -d ai_interviewer -f app/persistence/postgres/migrations/DEV-25_admin_override_tables.sql
```

Verify tables exist:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE '%_overrides'
ORDER BY table_name;
```

Expected: `coding_problem_overrides`, `question_overrides`, `role_overrides`, `rubric_overrides`, `template_overrides`, `topic_overrides`

Rollback:
```bash
psql -U jithsungh -d ai_interviewer -f app/persistence/postgres/migrations/DEV-25_admin_override_tables_rollback.sql
```

## File Map

| File | Purpose |
|---|---|
| `app/admin/persistence/__init__.py` | Public exports (10 repository classes) |
| `app/admin/persistence/models.py` | 20 SQLAlchemy ORM model classes |
| `app/admin/persistence/mappers.py` | Bidirectional entity ↔ model mappers |
| `app/admin/persistence/repositories.py` | 10 concrete repository implementations |
| `app/persistence/postgres/base.py` | Updated `import_all_models()` |
| `app/persistence/postgres/migrations/DEV-25_admin_override_tables.sql` | Forward migration |
| `app/persistence/postgres/migrations/DEV-25_admin_override_tables_rollback.sql` | Rollback migration |
| `tests/unit/admin/persistence/test_mappers.py` | 38 mapper tests |
| `tests/unit/admin/persistence/test_repositories.py` | 61 repository tests |
