# AI Prompts Layer Requirements

## 1. Purpose

The prompts layer provides **versioned prompt template management** with scope resolution and variable interpolation.

**Core Responsibilities:**

- Retrieve active prompt templates from `prompt_templates` table
- Resolve scope priority: organization-scoped → global fallback
- Render prompts with variable interpolation
- Support system/user prompt separation
- Track prompt version in telemetry
- Optional: context truncation and token estimation

**Design Principle:** Prompts are data, not code. All prompts stored in database for versioning and A/B testing.

---

## 2. Owned Tables

### Read-Only Access

- `prompt_templates` - Versioned prompt definitions

```sql
CREATE TABLE prompt_templates (
    id SERIAL PRIMARY KEY,
    prompt_type VARCHAR(50) NOT NULL,  -- 'question_generation', 'evaluation', etc.
    organization_id INTEGER REFERENCES organizations(id),  -- NULL = global
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT false,
    content TEXT NOT NULL,  -- Prompt template with variables: {{var}}
    system_prompt TEXT,     -- Optional system message
    model_id VARCHAR(100),  -- Preferred model for this prompt
    temperature FLOAT,      -- Suggested temperature
    max_tokens INTEGER,     -- Suggested max tokens
    metadata JSONB,         -- Additional config
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(prompt_type, organization_id, version),
    CHECK (version > 0)
);
```

**Scope Rules:**

- `organization_id = 1` and `scope = public` → Global prompt (visible to all organizations)
- `organization_id = X` → Organization-scoped (visible only to org X)
- Only ONE active version per (prompt_type, organization_id) pair

---

## 3. Input Constraints

### Prompt Retrieval

```python
def get_prompt(
    prompt_type: str,  # Required: 'question_generation' | 'evaluation' | 'resume_parsing' | etc.
    organization_id: Optional[int] = None,  # If None, global only
    fallback_to_global: bool = True  # If org-scoped not found, try global
) -> PromptTemplate:
    ...
```

**Validation:**

- `prompt_type` MUST be non-empty string
- `prompt_type` MUST exist in database (active version)
- If no active prompt found and `fallback_to_global=False` → raise PromptNotFoundError

### Prompt Rendering

```python
def render_prompt(
    template: PromptTemplate,
    variables: dict,  # Variable substitution mapping
    truncate_context: bool = False,
    max_context_tokens: Optional[int] = None
) -> RenderedPrompt:
    ...
```

**Validation:**

- `variables` MUST contain all required variables in template
- Variable values MUST be strings (or coercible to string)
- If `truncate_context=True`, `max_context_tokens` MUST be provided
- Template MUST have valid syntax (no unclosed `{{}}`)

### Variable Syntax

Templates use `{{variable_name}}` syntax:

```
Evaluate the candidate's answer to: {{question_text}}

Candidate Response:
{{candidate_response}}

Rubric Dimensions:
{{rubric_dimensions}}

Provide scores for each dimension.
```

---

## 4. Output Guarantees

### PromptTemplate Structure

```python
@dataclass
class PromptTemplate:
    id: int
    prompt_type: str
    organization_id: Optional[int]
    version: int
    content: str
    system_prompt: Optional[str]
    model_id: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    metadata: dict
    created_at: datetime
    is_active: bool
```

### RenderedPrompt Structure

```python
@dataclass
class RenderedPrompt:
    text: str                    # Rendered user prompt
    system_prompt: Optional[str] # Rendered system prompt
    model_id: Optional[str]      # Suggested model
    temperature: Optional[float] # Suggested temperature
    max_tokens: Optional[int]    # Suggested max tokens
    metadata: dict               # Prompt metadata
    version: int                 # Prompt version used
    variables_used: List[str]    # Variable names that were substituted
    truncated: bool              # Whether content was truncated
```

### Scope Resolution Guarantees

**Resolution Priority:**

1. Active organization-scoped prompt (if `organization_id` provided)
2. Active global prompt (if `fallback_to_global=True`)
3. Raise `PromptNotFoundError` (if no fallback)

**Invariant:**

```
For given (prompt_type, organization_id):
- At most ONE active version exists
- Version number MUST be max among all versions for that scope
```

---

## 5. Invariants

### Unique Active Version Invariant

```sql
-- Database constraint enforces this
CREATE UNIQUE INDEX idx_active_prompt_per_type_org
ON prompt_templates (prompt_type, organization_id)
WHERE is_active = true;
```

**Enforcement:** Activating new version MUST deactivate previous version atomically.

### Variable Completeness Invariant

```
ALL variables in template MUST be provided in render call
Missing variable → raise VariableMissingError with list of missing vars
```

**Enforcement:** Template parser extracts all `{{var}}` patterns, checks against provided variables.

### Prompt Versioning Invariant

```
Editing active prompt MUST create new version (never mutate active)
Version numbers MUST increment monotonically
```

**Enforcement:** Admin module handles versioning (prompts layer is read-only).

---

## 6. Forbidden Behaviors

### Data Mutations

- SHALL NOT write to `prompt_templates` table (read-only repository)
- SHALL NOT cache prompts indefinitely (use TTL-based cache if caching)
- SHALL NOT modify prompt content during rendering (only variable substitution)

### Security Violations

- SHALL NOT allow variable injection attacks (sanitize variables)
- SHALL NOT expose prompts across tenant boundaries
- SHALL NOT log full rendered prompts with PII in plaintext

### Domain Coupling

- SHALL NOT reference domain entities (interviews, evaluations, submissions)
- SHALL NOT perform business logic (scoring, template resolution)
- Prompts define HOW to query LLM, not WHAT to do with results

### Template Syntax

- SHALL NOT accept invalid template syntax (unclosed `{{`, unmatched `}}`)
- SHALL NOT silently skip missing variables
- SHALL NOT auto-create prompts (admin concern)

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `persistence/postgres` - Repository for `prompt_templates` table
- `shared/errors` - Exception types (PromptNotFoundError, VariableMissingError)
- `shared/observability` - Logging
- Template engine (Jinja2 or custom parser)

### Dependents (Outbound)

- Parent `ai` module - Retrieves prompts for LLM calls
- `ai/llm` - Uses rendered prompts with model/temperature suggestions

### External Dependencies

- **Jinja2** (optional) - Template rendering engine
- **tiktoken** (optional) - Token estimation for OpenAI models

---

## 8. Event Contracts Emitted

### Prompt Resolution Events

```json
{
  "event": "prompt.resolved",
  "prompt_type": "evaluation",
  "organization_id": 45,
  "version": 3,
  "scope": "organization",
  "fallback_used": false,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

```json
{
  "event": "prompt.fallback_to_global",
  "prompt_type": "question_generation",
  "organization_id": 45,
  "global_version": 2,
  "timestamp": "2026-02-13T10:35:00Z"
}
```

### Prompt Rendering Events

```json
{
  "event": "prompt.rendered",
  "prompt_type": "evaluation",
  "version": 3,
  "variables_count": 4,
  "truncated": false,
  "estimated_tokens": 1250,
  "timestamp": "2026-02-13T10:36:00Z"
}
```

---

## 9. Acceptance Criteria

### Prompt Retrieval

- [ ] Retrieve active global prompt by type
- [ ] Retrieve active organization-scoped prompt by type + org_id
- [ ] Organization-scoped prompt preferred over global
- [ ] Fallback to global if org-scoped not found (when enabled)
- [ ] Raise PromptNotFoundError if no active prompt exists
- [ ] Only one active version per (prompt_type, organization_id)

### Prompt Rendering

- [ ] Variables substituted correctly in template
- [ ] System prompt rendered separately (if present)
- [ ] Missing variable raises VariableMissingError with clear message
- [ ] Extra variables ignored (permissive)
- [ ] Model ID and temperature passed through to LLM layer
- [ ] Prompt version included in rendered output

### Variable Injection Safety

- [ ] HTML/SQL injection attempts sanitized
- [ ] Large variable values truncated with warning
- [ ] Newlines/special characters preserved correctly

### Context Truncation (Optional)

- [ ] If truncate_context=True, truncate to max_context_tokens
- [ ] Truncation prioritizes recent content (for conversation history)
- [ ] Truncated flag set in RenderedPrompt
- [ ] Token estimation accurate within 5% (for OpenAI models)

### Scope Resolution Edge Cases

- [ ] No global prompt, no org prompt → PromptNotFoundError
- [ ] Org prompt inactive, global active → Use global
- [ ] Both inactive → PromptNotFoundError
- [ ] Multiple versions exist, only active returned

---

## 10. Testing Guide

See [TESTING.md](TESTING.md) for comprehensive testing strategies.

**Key Testing Requirements:**

- Database integration tests for scope resolution
- Variable substitution edge cases
- Prompt versioning scenarios
- Token estimation accuracy (if implemented)

---

## 11. Edge Cases

### Variable Substitution Edge Cases

- **Nested variables:** `{{user_{{type}}}}` → Not supported, raise error
- **Variable name with spaces:** `{{ variable }}` → Strip whitespace, accept
- **Variable value is None:** Convert to empty string with warning
- **Variable value is list/dict:** Convert to JSON string representation
- **Variable value exceeds 50KB:** Truncate with warning, log full value separately

### Scope Resolution Edge Cases

- **Organization deleted:** Fallback to global (org prompts remain but unused)
- **Multiple active versions (data corruption):** Raise IntegrityError, log for admin
- **Prompt deactivated mid-request:** Stale read acceptable (eventual consistency)

### Template Syntax Edge Cases

- **Literal `{{}}` in text:** Escape with `\{{` and `\}}`
- **Unmatched braces:** Raise TemplateSyntaxError with position
- **Empty variable name `{{}}`:** Raise TemplateSyntaxError

### Token Estimation Edge Cases

- **Non-English text:** Token counts approximate (acceptable variance: 10%)
- **Code blocks:** Token counts may differ from prose (use conservative estimate)
- **Special characters:** Estimate may overcount (prefer overestimate to underestimate)

---

## 12. Concurrency Concerns

### Prompt Caching

- Optional: Cache active prompts in-memory with TTL (60 seconds)
- Cache key: `(prompt_type, organization_id)`
- Cache invalidation: TTL-based (no explicit invalidation)
- Cache MUST be thread-safe (use `threading.Lock` or immutable cache)

### Database Reads

- Prompt retrieval is read-only (no locking required)
- Multiple concurrent reads acceptable
- Stale reads acceptable (prompt changes are infrequent)

### Version Activation

- Activating new version (admin action) uses transaction:
  ```sql
  BEGIN;
  UPDATE prompt_templates SET is_active = false WHERE prompt_type = ? AND organization_id = ? AND is_active = true;
  UPDATE prompt_templates SET is_active = true WHERE id = ?;
  COMMIT;
  ```
- Prompts layer only reads, no coordination needed

---

## 13. Prompt Template Examples

### Question Generation Template

```
System Prompt:
You are an expert technical interviewer. Generate insightful questions based on the candidate's background and role requirements.

User Prompt:
Role: {{role}}
Topics: {{topics}}
Difficulty: {{difficulty}}

{% if resume_context %}
Candidate Background:
{{resume_context}}
{% endif %}

{% if previous_questions %}
Already Asked:
{{previous_questions}}
{% endif %}

Generate a unique, role-appropriate question. Return JSON:
{
  "question_text": "...",
  "difficulty": "easy|medium|hard",
  "expected_answer_outline": "...",
  "followup_suggestions": [...]
}
```

### Evaluation Template

```
System Prompt:
You are an objective evaluator. Score the candidate's response against each rubric dimension.

User Prompt:
Question:
{{question_text}}

Candidate Response:
{{candidate_response}}

Rubric Dimensions:
{{rubric_dimensions}}

Evaluate each dimension. Return JSON:
{
  "dimension_scores": [
    {
      "dimension_name": "...",
      "score": <number>,
      "justification": "..."
    }
  ],
  "overall_comment": "..."
}
```

### Resume Parsing Template

```
Extract structured information from the resume below. Return JSON.

Resume Text:
{{resume_text}}

Expected JSON Schema:
{
  "skills": [<list of skills>],
  "experience_years": <number>,
  "education": [{degree, institution, year}],
  "projects": [{title, description, technologies}],
  "confidence_score": <0.0 to 1.0>
}
```

---

## 14. Prompt Versioning Workflow

### Creating New Version (Admin Action)

1. Admin edits prompt content in UI
2. Admin module creates new `prompt_templates` entry:
   - `version = max(version) + 1` for this (prompt_type, organization_id)
   - `is_active = false` initially
3. Admin tests new version (preview mode)
4. Admin activates new version:
   - Atomic update: deactivate old, activate new
   - Previous version remains in database (audit trail)

### Prompts Layer Behavior

- Always retrieves active version
- Never modifies prompts
- Logs prompt version in telemetry for debugging

---

**End of AI Prompts Layer Requirements**
