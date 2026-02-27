# Human Testing Guide — `auth/persistence`

## Ticket: DEV-26 | Module: `app/auth/persistence`

---

## 1. Prerequisites

| Requirement | How to verify |
|---|---|
| PostgreSQL 17.x running | `psql -h <host> -U postgres -c "SELECT version();"` |
| Schema applied | `psql -c "\dt public.*"` → tables `users`, `admins`, `candidates`, `refresh_tokens`, `auth_audit_log`, `organizations` present |
| Python venv active | `which python` → `.venv/bin/python` |
| Dependencies installed | `pip install -r requirements.txt` |
| `TEST_DATABASE_URL` set (optional) | Defaults to `postgresql://postgres:interviewer%40password@100.95.213.103/interviewer` |

---

## 2. Running the Automated Test Suite

### Unit tests (no DB required)

```bash
python -m pytest tests/unit/auth/persistence/ -v
```

**Expected:** 90 passed.

### Integration tests (requires PostgreSQL)

```bash
python -m pytest tests/integration/auth/persistence/ -v -m integration
```

**Expected:** 51 passed.

### Full suite

```bash
python -m pytest tests/unit/auth/persistence/ tests/integration/auth/persistence/ -v
```

**Expected:** 141 passed.

---

## 3. Manual Verification via `psql`

Since this is a persistence layer (no HTTP endpoints), manual testing validates the DB schema, constraints, and data integrity directly.

### 3.1 Connect to the database

```bash
psql "postgresql://postgres:interviewer%40password@100.95.213.103/interviewer"
```

### 3.2 Verify enum types exist

```sql
SELECT typname, enumlabel
FROM pg_enum e
JOIN pg_type t ON e.enumtypid = t.oid
WHERE typname IN ('user_status', 'admin_role', 'admin_status', 'candidate_plan')
ORDER BY typname, enumsortorder;
```

**Expected values:**

| Type | Values |
|---|---|
| `user_status` | `active`, `inactive`, `banned` |
| `admin_role` | `superadmin`, `admin`, `read_only` |
| `admin_status` | `active`, `inactive`, `suspended` |
| `candidate_plan` | `free`, `pro`, `prime` |

### 3.3 Verify table structures

```sql
\d+ users
\d+ admins
\d+ candidates
\d+ refresh_tokens
\d+ auth_audit_log
```

### 3.4 Test UNIQUE constraints

```sql
-- Insert a user
INSERT INTO users (name, email, password_hash, user_type, status, token_version)
VALUES ('Test', 'unique-test@test.com', 'hash', 'candidate', 'active', 1);

-- Attempt duplicate → should fail
INSERT INTO users (name, email, password_hash, user_type, status, token_version)
VALUES ('Test2', 'unique-test@test.com', 'hash2', 'admin', 'active', 1);
-- Expected: ERROR: duplicate key value violates unique constraint "users_email_key"

-- Clean up
DELETE FROM users WHERE email = 'unique-test@test.com';
```

### 3.5 Test CHECK constraint

```sql
INSERT INTO users (name, email, password_hash, user_type, status, token_version)
VALUES ('Bad', 'bad@test.com', 'hash', 'superadmin', 'active', 1);
-- Expected: ERROR: new row ... violates check constraint "users_user_type_check"
```

### 3.6 Test FK cascade

```sql
-- Insert user + candidate
INSERT INTO users (name, email, password_hash, user_type, status, token_version)
VALUES ('Cascade', 'cascade@test.com', 'hash', 'candidate', 'active', 1)
RETURNING id;  -- note the id

INSERT INTO candidates (user_id, plan, status)
VALUES (<returned_id>, 'free', 'active');

-- Delete user → candidate should cascade
DELETE FROM users WHERE email = 'cascade@test.com';

-- Verify candidate gone
SELECT * FROM candidates WHERE user_id = <returned_id>;
-- Expected: 0 rows
```

### 3.7 Verify audit log immutability contract

The `auth_audit_log` table allows INSERTs only at the repository level. The DB has no physical DENY trigger, but the repository contract forbids UPDATE/DELETE. Verify no such methods exist:

```bash
grep -n "def update\|def delete" app/auth/persistence/audit_log_repository.py
# Expected: no output
```

---

## 4. Smoke Test via Python REPL

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
python
```

```python
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres
from app.persistence.postgres.session import init_session_factory, get_session_factory

# Initialize
config = DatabaseSettings(
    database_url="postgresql://postgres:interviewer%40password@100.95.213.103/interviewer"
)
init_postgres(config)
init_session_factory()

# Get session
session = get_session_factory()()

# Test UserRepository
from app.auth.persistence.user_repository import UserRepository
repo = UserRepository(session)

# Read (safe — no writes)
user = repo.find_by_email("some-existing-email@example.com")
print(f"Found: {user}")

exists = repo.email_exists("nonexistent@test.com")
print(f"Email exists: {exists}")  # False

# Test AuditLogRepository
from app.auth.persistence.audit_log_repository import AuthAuditLogRepository
audit_repo = AuthAuditLogRepository(session)
from datetime import datetime, timezone, timedelta
since = datetime.now(timezone.utc) - timedelta(hours=1)
count = audit_repo.get_failed_login_attempts("test@example.com", since=since)
print(f"Failed logins: {count}")

# Cleanup
session.rollback()
session.close()
```

---

## 5. Common Failure Scenarios & Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `NoReferencedTableError: ... organizations` | Auth models use own `Base`, `organizations` table not in MetaData | Integration conftest registers stub table; verify conftest is loaded |
| `InvalidTextRepresentation: invalid input value for enum` | Passing value not in PostgreSQL enum type | Check `user_status`, `admin_status`, `candidate_plan` allowed values above |
| `ConflictError` on create | UNIQUE constraint violation (email, user_id+org_id, token_hash) | Verify no duplicate data in target table |
| `DatabaseError` on create | NOT NULL, FK, or CHECK constraint violation | Verify all required fields are populated with valid values |
| Connection refused | PostgreSQL not running or wrong URL | Check `TEST_DATABASE_URL` env var, verify `pg_isready` |

---

## 6. Files Delivered

### Repository Classes (`app/auth/persistence/`)

| File | Purpose |
|---|---|
| `models.py` | ORM models for 5 auth tables (pre-existing, column fix applied) |
| `user_repository.py` | CRUD for `users` table |
| `admin_repository.py` | CRUD for `admins` table |
| `candidate_repository.py` | CRUD + JSONB merge for `candidates` table |
| `refresh_token_repository.py` | CRUD + revocation + cleanup for `refresh_tokens` |
| `audit_log_repository.py` | INSERT-only + read queries for `auth_audit_log` |
| `__init__.py` | Barrel exports for all models + repositories |

### Unit Tests (`tests/unit/auth/persistence/`)

| File | Test count |
|---|---|
| `test_models.py` | 22 tests |
| `test_user_repository.py` | 15 tests |
| `test_admin_repository.py` | 12 tests |
| `test_candidate_repository.py` | 13 tests |
| `test_refresh_token_repository.py` | 14 tests |
| `test_audit_log_repository.py` | 14 tests |

### Integration Tests (`tests/integration/auth/persistence/`)

| File | Test count |
|---|---|
| `conftest.py` | Shared fixtures (DB init, session, test data factories) |
| `test_user_repository.py` | 13 tests |
| `test_admin_repository.py` | 9 tests |
| `test_candidate_repository.py` | 9 tests |
| `test_refresh_token_repository.py` | 10 tests |
| `test_audit_log_repository.py` | 10 tests |
