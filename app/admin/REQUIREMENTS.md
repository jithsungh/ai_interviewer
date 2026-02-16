# Admin Module Requirements

## 1. Purpose

The Admin module serves as the **configuration and control-plane boundary** for the AI Interviewer system. It manages non-runtime state including:

- Interview templates (structure, versioning, activation)
- Rubrics and evaluation criteria definitions
- Roles and their topic associations
- Interview submission windows (scheduling)
- Window-role-template mappings
- Template immutability enforcement after use

**Key Principle:** Admin operations configure "what can happen" but never interfere with active interview runtime. Once a template is referenced by a submission, it becomes immutable.

**References:**

- SRS: FR-1.4, FR-2.3, FR-8.2, FR-8.3, FR-8.5
- Architecture: Control-plane logic (non-runtime state)
- ERD: Architecture Invariant #3 (Template Immutability After Use)

---

## 2. Owned Tables

### Primary Ownership

**Base Content Tables (Super Org owned, org_id=1):**

- `interview_templates` - Template definitions with structure and rules
- `interview_template_roles` - Template-to-role mappings
- `interview_template_rubrics` - Template-to-rubric-to-section mappings
- `rubrics` - Evaluation rubric definitions
- `rubric_dimensions` - Dimension scoring criteria per rubric
- `roles` - Role definitions (scope: global/organization)
- `topics` - General interview topics (behavioral, technical, situational)
- `coding_topics` - Specialized coding problem topics
- `questions` - Behavioral and technical questions
- `coding_problems` - Coding assessment problems
- `interview_submission_windows` - Scheduling windows with access control
- `window_role_templates` - Direct window-role-template mapping

**Override Tables (Tenant-specific modifications):**

- `template_overrides` - Tenant-specific template field overrides
- `rubric_overrides` - Tenant-specific rubric modifications
- `role_overrides` - Tenant-specific role customizations
- `topic_overrides` - Tenant-specific topic modifications
- `question_overrides` - Tenant-specific question customizations
- `coding_problem_overrides` - Tenant-specific coding problem modifications

### Read-Only Access

- `organizations` - Tenant context for multi-tenancy enforcement
- `admins` - Authorization verification (superadmin, admin, read_only roles)
- `interview_submissions` - Check if template is in use (immutability enforcement)

### Content Ownership Model

**Super Organization (org_id=1) - Project Owner:**
- Owns ALL base content (templates, rubrics, roles, topics, questions, coding_problems)
- Base content serves as canonical seed data for all tenants
- Base content is visible to all tenants (read-only)
- Can create/edit base content directly (superadmin only)

**Tenant Organizations (org_id != 1):**
- Can create native content within their organization boundary
- Can customize super org content via override tables
- Overrides are tenant-scoped and isolated
- Cannot modify base content directly

---

## 3. Input Constraints

### Authentication & Authorization

- All requests MUST include valid JWT with admin role claims
- **RBAC enforcement with 3 role types:**
  - `superadmin`: Full access to super org (org_id=1) base content and all tenant operations
  - `admin`: Full CRUD on tenant-owned content and override management
  - `read_only`: View-only access to tenant-scoped content and effective merged views
- Multi-tenancy: Operations MUST be scoped to authenticated admin's organization
- Cross-tenant operations SHALL NOT be permitted (NFR-7.1)
- **Role-specific permissions:**
  - `superadmin`: Create/edit/delete base content, manage all overrides, cross-tenant visibility
  - `admin`: Create/edit/delete native tenant content, manage own overrides, tenant-scoped visibility
  - `read_only`: GET operations only, effective merged view (base + overrides), tenant-scoped visibility

### Content Management (All Content Types)

All managed content follows the same override pattern:
- Templates
- Rubrics
- Roles
- Topics (general and coding)
- Questions (behavioral/technical)
- Coding Problems

#### Super Organization (org_id=1) - Project Owner

- **Superadmin only** can create/edit base content directly
- Base content is immutable once referenced by ANY tenant submission
- Versioning applies to base content when modifications are needed post-usage
- Base content is visible to all tenants as read-only canonical data

#### Tenant Organizations (org_id != 1)

- **Creating Native Content:** Full CRUD on content with `organization_id = <tenant_id>`
- **Modifying Super Org Content:** CANNOT edit base content directly
  - MUST create entry in corresponding `*_overrides` table
  - Override contains only modified fields (JSONB sparse overlay)
  - Override is tenant-scoped and does not affect other tenants
  - Overrides apply to: templates, rubrics, roles, topics, questions, coding_problems
- **Override Constraints:**
  - `base_*_id` MUST reference active super org content
  - Override fields MUST be valid JSON subset of content structure
  - Cannot override immutable fields (id, organization_id, scope)
  - Override must maintain structural integrity of base content

#### Query Resolution (Runtime)

```python
# Generic override resolution pattern
effective_content = merge(
    base_content,           # From super org (org_id=1)
    tenant_override         # If exists for this tenant
)

# Example: Template resolution
effective_template = get_effective_template(base_template_id, tenant_org_id)

# Example: Question resolution
effective_question = get_effective_question(base_question_id, tenant_org_id)
```

### Admin UI Integration

The admin interface provides:

1. **Content Management:**
   - Question Bank (behavioral/technical questions)
   - Coding Problems management
   - Template versioning and publishing
   - Rubric definition with dimension weighting

2. **Scheduling:**
   - Interview submission windows
   - Role-template-window mappings
   - Proctoring configuration

3. **Monitoring & Review:**
   - Live interview monitoring
   - Flagged submission review queue
   - Human oversight and score overrides

4. **Governance:**  (least priority, can be ignored now)
   - Audit logs
   - Retention policies
   - Consent management
   - Deletion requests

5. **System Configuration:**
   - Admin user management (superadmin/admin/read_only)
   - AI model registry
   - Prompt templates
   - Feature flags

### Rubric Management

- Rubric schema MUST be valid JSONB
- Dimensions MUST have: name, description, max_score, weight, criteria
- Dimension weights MUST sum to 1.0 per rubric
- Dimension sequence_order MUST be unique within rubric

### Role & Topic Management

- Role names MUST be unique within scope (global or per organization)
- Topic hierarchies: parent_topic_id references within same scope
- Circular references forbidden in topic trees

### Window Management

- `end_time` MUST be > `start_time`
- `start_time` and `end_time` MUST include timezone
- Window-role-template mappings: role and template MUST exist and be active
- Selection weights MUST be positive integers

---

## 4. Output Guarantees

### Idempotency

- GET operations: Always return current state
- PUT/PATCH: Repeated identical requests produce same final state
- POST: Template/rubric creation with duplicate names SHALL fail with conflict error

### Audit Trail

- All mutations logged in `audit_logs` table with:
  - Actor user ID
  - Action type (create/update/delete/activate)
  - Entity type and ID
  - Old and new values (JSON)
  - Timestamp and IP address

### Versioning

- Template edits when in-use SHALL create new version entry
- Previous versions remain immutable and queryable
- Version history SHALL be traversable

### Consistency

- Cross-table references SHALL maintain referential integrity
- Activation SHALL be atomic with validation
- Deactivation SHALL cascade appropriately (e.g., deactivate templates using deactivated rubric)

---

## 5. Invariants

### Template Immutability After Use

**Invariant #3 from ERD:**

```
IF EXISTS (
  SELECT 1 FROM interview_submissions
  WHERE template_id = T.id
)
THEN template_structure of T SHALL NOT be modified
```

**Enforcement:** Check before update; if violated, create new version instead

**Override Behavior:**

- Base template immutability applies to super org content
- Tenant overrides can still be created/modified (they layer on top)
- Override changes do NOT violate base template immutability

### Single Source of Truth

- Role targeting: Use `interview_template_roles` table (NOT `role_category` text field)
- No duplicate template names within same organization and scope
- No duplicate rubric names within same organization and scope
- No duplicate override per (organization_id, base_template_id) pair

### Window Integrity

- Active windows MUST NOT overlap for same role if `allow_resubmission=false`
- Windows MUST have at least one window_role_template mapping

### Scope Enforcement & Override Hierarchy

#### Base Content (Super Org - org_id=1)

- Super org content is visible to ALL tenants (read-only)
- Acts as canonical/seed data provided by project owner
- Versioned independently
- Applies to: templates, rubrics, roles, topics, questions, coding_problems

#### Tenant Native Content

- Tenant-created content visible only to owning organization
- Full CRUD within tenant boundary
- Can reference super org base content OR own native content
- Applies to all content types

#### Override Layering Rules

1. **Override Priority:** Tenant override > Base content
2. **Override Scope:** Overrides apply only to owning tenant
3. **Partial Overrides:** Can override specific fields, inherit rest from base
4. **Override Deletion:** Deleting override reverts to base content
5. **Base Deletion:** Deactivating base content cascades to all tenant overrides (mark stale)
6. **Multi-Content Support:** Override pattern applies to all managed content types
7. **Isolation:** Tenant A's overrides are invisible to Tenant B

#### Override Table Schema Pattern

All override tables follow this structure:
```sql
CREATE TABLE <content_type>_overrides (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    base_<content_type>_id BIGINT NOT NULL REFERENCES <content_type>(id),
    override_fields JSONB NOT NULL,  -- Sparse field overrides
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(organization_id, base_<content_type>_id)
);
```

Examples:
- `template_overrides(organization_id, base_template_id, override_fields)`
- `question_overrides(organization_id, base_question_id, override_fields)`
- `coding_problem_overrides(organization_id, base_coding_problem_id, override_fields)`

---

## 6. Forbidden Behaviors

### Runtime Interference

- Admin operations SHALL NOT modify active interview sessions
- Template changes SHALL NOT affect in-progress submissions
- Window closure SHALL NOT terminate active interviews (only prevent new starts)

### Security Violations

- SHALL NOT expose content across tenant boundaries (NFR-7.1)
- SHALL NOT allow editing of content owned by other organizations
- SHALL NOT allow tenants to directly edit super org base content
- SHALL NOT allow overrides on non-super-org content (overrides only apply to org_id=1 base)
- SHALL NOT expose other tenants' overrides
- SHALL NOT bypass RBAC checks
- **Role-specific restrictions:**
  - `read_only` admins SHALL NOT mutate data
  - `admin` SHALL NOT access super org base content modification
  - Only `superadmin` can modify base content (org_id=1)
  - `admin` and `read_only` SHALL NOT have cross-tenant visibility

### Data Integrity

- SHALL NOT delete content referenced by submissions (soft delete or archive only)
- SHALL NOT create orphaned window_role_templates (missing role/template)
- SHALL NOT modify content without validation passing
- SHALL NOT create overrides for non-existent base content
- SHALL NOT create overrides for content not owned by super org (org_id=1)
- SHALL NOT create duplicate overrides (organization_id, base_*_id uniqueness)
- SHALL NOT allow override fields that violate base content schema

### Schema Violations

- SHALL NOT store invalid JSON in template_structure
- SHALL NOT accept rubric dimensions with weights summing != 1.0
- SHALL NOT create circular topic hierarchies

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `shared/auth_context` - Request-scoped tenant and user resolution
- `shared/errors` - Custom exception types (ValidationError, ConflictError, etc.)
- `persistence/postgres` - Database session and models
- `shared/observability` - Logging and audit instrumentation

### Dependents (Outbound)

- `interview/orchestration` - Reads templates, rubrics, roles for session initialization
- `interview/session` - Validates window access at submission creation
- `evaluation/scoring` - Reads rubrics for evaluation
- `evaluation/snapshots` - Captures frozen rubric/template context
- `question/selection` - Uses topic filters from templates

### External Systems

- PostgreSQL for transactional storage
- Redis for caching frequently accessed templates/rubrics (optional)

---

## 8. Event Contracts Emitted

### Internal Events (Message Bus / Event Log)

#### Template Events

```json
{
  "event": "template.created",
  "template_id": 123,
  "organization_id": 45,
  "scope": "organization",
  "version": 1,
  "timestamp": "2026-02-13T10:30:00Z"
}

{
  "event": "template.activated",
  "template_id": 123,
  "organization_id": 45,
  "timestamp": "2026-02-13T10:35:00Z"
}

{
  "event": "template.versioned",
  "old_template_id": 123,
  "new_template_id": 124,
  "organization_id": 45,
  "reason": "immutability_enforcement",
  "timestamp": "2026-02-13T11:00:00Z"
}
```

#### Override Events

```json
{
  "event": "template_override.created",
  "override_id": 456,
  "organization_id": 45,
  "base_template_id": 123,
  "overridden_fields": ["name", "description"],
  "timestamp": "2026-02-13T10:45:00Z"
}

{
  "event": "template_override.updated",
  "override_id": 456,
  "organization_id": 45,
  "base_template_id": 123,
  "changed_fields": ["description"],
  "timestamp": "2026-02-13T11:15:00Z"
}

{
  "event": "template_override.deleted",
  "override_id": 456,
  "organization_id": 45,
  "base_template_id": 123,
  "reverted_to_base": true,
  "timestamp": "2026-02-13T12:00:00Z"
}
```

#### Rubric Events

```json
{
  "event": "rubric.created",
  "rubric_id": 78,
  "organization_id": 45,
  "dimension_count": 5,
  "timestamp": "2026-02-13T09:00:00Z"
}

{
  "event": "rubric.deactivated",
  "rubric_id": 78,
  "affected_templates": [123, 124],
  "timestamp": "2026-02-13T12:00:00Z"
}
```

#### Window Events

```json
{
  "event": "window.created",
  "window_id": 456,
  "organization_id": 45,
  "scope": "only_invited",
  "start_time": "2026-03-01T00:00:00Z",
  "end_time": "2026-03-15T23:59:59Z",
  "timestamp": "2026-02-13T10:00:00Z"
}

{
  "event": "window.opened",
  "window_id": 456,
  "timestamp": "2026-03-01T00:00:00Z"
}

{
  "event": "window.closed",
  "window_id": 456,
  "timestamp": "2026-03-15T23:59:59Z"
}
```

### Audit Log Entries

All mutations recorded in `audit_logs` table per NFR-11.1, NFR-11.2

---

## 9. Acceptance Criteria

### Template Management (FR-8.5)

- [ ] Admin can create template with valid structure
- [ ] System validates template structure against schema before save
- [ ] System prevents activation if validation fails
- [ ] Activated template appears in selection for new windows
- [ ] Attempting to edit in-use template creates new version instead
- [ ] Previous versions remain queryable with full history

### Rubric Management (FR-6.1, NFR-10)

- [ ] Admin can define rubric with multiple dimensions
- [ ] System enforces dimension weight sum = 1.0
- [ ] Deactivating rubric logs affected templates
- [ ] Rubric changes do not affect existing evaluations

### Window Scheduling (FR-2.3)

- [ ] Admin can create window with start/end times
- [ ] System enforces end_time > start_time
- [ ] Window-role-template mappings validated at creation
- [ ] Overlapping windows rejected if resubmission disabled
- [ ] Closed windows prevent new submissions but preserve existing data

### Multi-Tenancy with Override Pattern (NFR-7.1)

- [ ] Super org (id=1) can create/edit base templates directly
- [ ] Base templates visible to all tenants (read-only)
- [ ] Tenant from Org A cannot directly edit super org base templates
- [ ] Tenant from Org A can create override on super org template
- [ ] Override stored in `template_overrides` with `organization_id=A`
- [ ] Tenant A queries template → receives merged (base + override A)
- [ ] Tenant B queries same template → receives merged (base + override B or just base)
- [ ] Tenant A cannot see/edit Tenant B's overrides
- [ ] Tenant can create native templates (organization_id=A) with full CRUD
- [ ] Attempting to override non-super-org content returns 403 Forbidden
- [ ] Deleting override reverts tenant view to base content
- [ ] Deactivating base template marks all tenant overrides as stale

### Immutability Enforcement (ERD Invariant #3)

- [ ] Editing unused template succeeds
- [ ] Editing used template creates new version
- [ ] Old version remains unchanged and linked
- [ ] Version number increments correctly

### RBAC (NFR-7)

- [ ] `read_only` admin can GET but not POST/PUT/DELETE
- [ ] `admin` can manage templates within own organization
- [ ] `superadmin` can manage global templates
- [ ] Unauthorized actions return 403 Forbidden

---

## 10. Testing Guide

### Unit Tests

- **Domain Logic:**
  - Template structure validation (valid/invalid JSON schemas)
  - Rubric dimension weight validation (sum to 1.0)
  - Immutability check logic (in-use detection)
  - Version increment logic

- **Repository Layer:**
  - CRUD operations with mocked database
  - Multi-tenancy filtering (verify WHERE clauses)
  - Soft delete vs hard delete behavior

### Integration Tests

- **API Endpoints:**
  - POST /api/v1/templates - Create valid template
  - POST /api/v1/templates - Reject invalid structure
  - PUT /api/v1/templates/{id}/activate - Activation success
  - PUT /api/v1/templates/{id} - Edit unused template (success)
  - PUT /api/v1/templates/{id} - Edit used template (creates version)
  - DELETE /api/v1/templates/{id} - Soft delete unused template
  - DELETE /api/v1/templates/{id} - Reject delete of used template

- **Window Management:**
  - POST /api/v1/windows - Valid window creation
  - POST /api/v1/windows - Reject overlapping windows
  - GET /api/v1/windows/active - Return only open windows

### Security Tests

- **Tenant Isolation:**
  - Create template as Org A admin
  - Attempt GET as Org B admin (expect 404 or 403)
  - Attempt PUT as Org B admin (expect 403)

- **RBAC:**
  - Authenticate as `read_only`
  - Attempt POST/PUT/DELETE (expect 403)
  - Verify GET succeeds

### Performance Tests

- **Template Retrieval:**
  - Load 1000 templates, query by organization (target: <100ms)
  - Verify caching reduces repeated queries

- **Bulk Operations:**
  - Create 100 rubrics in parallel
  - Activate 50 templates concurrently
  - Verify no deadlocks or race conditions

---

## 11. Edge Cases

### Template Versioning

- **Simultaneous edits:** Two admins edit same template concurrently
  - Expected: Optimistic locking prevents lost updates; second edit creates new version from latest
- **Rapid versioning:** Admin creates 10 versions in 1 minute
  - Expected: All versions logged, version numbers sequential

### Window Timing

- **Submission at exact boundary:** Candidate submits at `end_time` timestamp
  - Expected: `allow_after_end_time` flag determines acceptance
- **Timezone confusion:** Window in UTC, candidate in PST
  - Expected: All times stored/compared in UTC, UI converts to candidate timezone

### Rubric Deletion

- **Delete rubric used by 100 templates**
  - Expected: Soft delete, mark `is_active=false`, cascade deactivation to templates (optional)
  - Alternative: Reject deletion with error listing affected templates

### Orphaned References

- **Delete role referenced by window_role_templates**
  - Expected: Foreign key constraint prevents deletion OR cascade delete mappings
- **Deactivate template after window opens**
  - Expected: Window remains valid (template was valid at window creation)

### Scope Conflicts

- **Organization template references global rubric (allowed)**
  - Expected: Success
- **Global template references organization rubric (forbidden)**
  - Expected: Validation error at creation/activation

### Large Payloads

- **Template with 50KB JSON structure**
  - Expected: Accept if valid schema, store in JSONB
- **Rubric with 100 dimensions**
  - Expected: Accept, verify weight sum = 1.0

---

## 12. Concurrency Concerns

### Race Conditions

#### Template Activation Race

**Scenario:** Two admins activate same template simultaneously

- **Risk:** Duplicate activation events, inconsistent state
- **Mitigation:** Idempotent activation (check `is_active` before update), database-level unique constraint on state transitions

#### Template Edit + Submission Creation Race

**Scenario:**

1. Admin checks template (not in use) at T0
2. Candidate creates submission with template at T1
3. Admin edits template at T2 (believes still unused)

- **Risk:** Template modified after submission references it
- **Mitigation:** Use database transaction with `SELECT FOR UPDATE` on template before checking usage

#### Version Number Collision

**Scenario:** Two admins trigger versioning simultaneously

- **Risk:** Both get version=2, collision on insert
- **Mitigation:** Database unique constraint on (template_name, organization_id, version), retry logic on conflict

### Deadlock Scenarios

#### Window-Role-Template Circular Lock

**Scenario:**

- Transaction A: Lock window W1, then role R1
- Transaction B: Lock role R1, then window W1

- **Mitigation:** Consistent lock ordering (always lock in order: window → role → template)

#### Rubric-Template Update Deadlock

**Scenario:**

- Transaction A: Update rubric R1, then validate template T1
- Transaction B: Update template T1, then validate rubric R1

- **Mitigation:** Acquire locks in fixed order: rubrics before templates

### Optimistic Locking

- Use `updated_at` timestamp or version column for optimistic concurrency control
- On conflict, return 409 Conflict with current state
- Client retries with updated data

### Event Ordering

- Ensure audit logs written in transaction commit order
- Use database sequences or ULID for globally ordered event IDs
- Event emission may be asynchronous but must preserve causality

### Cache Invalidation

- On template/rubric update: Invalidate Redis cache entries
- Use cache keys with version: `template:{id}:{version}`
- Race between update and cache read: Accept eventual consistency (cache TTL: 5 minutes)

---

## Summary

The **Admin module** is the configuration command center, enforcing strict immutability once templates enter production use. It balances flexibility for administrators with safety guarantees for running interviews. All operations are scoped to tenants, logged for audit, and validated before activation. The module must handle concurrent edits gracefully while maintaining referential integrity across templates, rubrics, roles, and windows.
