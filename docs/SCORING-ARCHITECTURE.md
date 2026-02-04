# Interview Scoring Architecture

## 🎯 Core Principle

> **Scores are facts. Rules are context. Context must be snapshotted.**

## Design Decision: Snapshot + Derivation (Hybrid)

### ❌ NOT Purely Dynamic

- Results would change when rubrics/templates evolve
- Expensive joins across many tables
- Hard to explain discrepancies
- Impossible to audit reliably

### ❌ NOT Purely Stored/Flattened

- Already have normalized truth in evaluations
- Duplication invites inconsistency
- Lose drill-down capability

### ✅ Hybrid Approach

- **Compute** per-exchange scores once
- **Store** frozen overall interview result
- **Keep** it derivable for audit/debug

---

## Data Flow: Computation Pipeline

```
interview_exchanges
  → evaluations
    → evaluation_dimension_scores
      → aggregate per exchange
        → aggregate per section
          → apply template weights
            → normalize
              → store interview_results
```

---

## Table: `interview_results`

### Purpose

Authoritative, frozen snapshot of interview scoring with full context.

### Schema

```sql
interview_results (
  id bigserial pk,
  interview_submission_id bigint unique,  -- one per version

  -- Final outputs
  final_score numeric not null,
  normalized_score numeric,               -- percentage 0-100
  result_status text not null,            -- pass, fail, borderline, incomplete
  recommendation text,                    -- hire, no_hire, review, strong_hire

  -- Scoring context snapshots (immutable)
  scoring_version text not null,          -- v1.0, v2-review, etc.
  rubric_snapshot jsonb not null,         -- rubric ids + dimension weights used
  template_weight_snapshot jsonb not null,-- section weights from template

  -- Section-wise breakdown (for UI)
  section_scores jsonb not null,          -- {resume: 8.5, coding: 32.0, ...}

  -- Qualitative assessment
  strengths text,
  weaknesses text,
  summary_notes text,

  -- Metadata
  generated_by text not null,
  model_id bigint,
  is_current boolean not null,            -- latest version flag
  computed_at timestamptz not null,
  created_at timestamptz not null,

  UNIQUE (interview_submission_id, scoring_version)
);
```

---

## Snapshot Formats (Concrete Examples)

### 1. `template_weight_snapshot`

Frozen section weights from `interview_templates.template_structure` at time of evaluation.

```json
{
  "resume_analysis": { "weight": 10, "max_score": 10 },
  "self_introduction": { "weight": 5, "max_score": 5 },
  "topics_assessment": { "weight": 35, "max_score": 35 },
  "coding_round": { "weight": 40, "max_score": 40 },
  "complexity_analysis": { "weight": 10, "max_score": 10 }
}
```

**Why critical:** Templates are versioned, but this guarantees old interviews use old weights.

---

### 2. `rubric_snapshot`

Minimal snapshot of rubrics used (not full verbose copy).

```json
{
  "rubric_id": 12,
  "rubric_name": "Technical Assessment Rubric v3",
  "dimensions": [
    {
      "dimension_id": 1,
      "name": "clarity",
      "weight": 0.3,
      "max_score": 5
    },
    {
      "dimension_id": 2,
      "name": "correctness",
      "weight": 0.5,
      "max_score": 5
    },
    {
      "dimension_id": 3,
      "name": "depth",
      "weight": 0.2,
      "max_score": 5
    }
  ]
}
```

**Rule:** Only copy IDs + weights. Do not duplicate full criteria JSON unless legally required.

---

### 3. `section_scores`

UI-friendly breakdown by interview section.

```json
{
  "resume_analysis": 8.5,
  "self_introduction": 4.0,
  "topics_assessment": 27.5,
  "coding_round": 32.0,
  "complexity_analysis": 6.5
}
```

These sum to `final_score` (may apply normalization).

---

## Computation Triggers

### When to Compute

✅ **On submission completion**

- Candidate submits interview
- All exchanges evaluated
- Async job computes final result

✅ **Manual reviewer override**

- Human reviewer adjusts scores
- Create new version with `scoring_version = 'v2-review'`
- Set old version `is_current = false`

### When NOT to Recompute

❌ Rubric edited
❌ Template edited
❌ Model updated
❌ Exchange re-evaluated (unless explicitly triggered)

---

## Versioning Strategy

### Never Overwrite Results

If re-evaluation happens:

```sql
INSERT INTO interview_results (
  interview_submission_id,
  scoring_version,
  is_current,
  ...
) VALUES (
  123,
  'v2-review',  -- new version
  true,
  ...
);

UPDATE interview_results
SET is_current = false
WHERE interview_submission_id = 123
  AND scoring_version = 'v1.0';
```

### Version Naming Convention

- `v1.0` - Initial automated scoring
- `v1.1` - Minor adjustment (same rubric/template)
- `v2-review` - Manual reviewer override
- `v3-appeal` - After candidate appeal
- `v4-audit` - Compliance re-evaluation

---

## What to Store vs. Derive

### ✅ Store (Authoritative)

| Field                      | Reason                       |
| -------------------------- | ---------------------------- |
| `final_score`              | Rankings, decisions, audit   |
| `section_scores`           | Explainability, UI breakdown |
| `template_weight_snapshot` | Template may change          |
| `rubric_snapshot`          | Rubric may change            |
| `result_status`            | Business outcome (pass/fail) |
| `scoring_version`          | Reproducibility              |

### ❌ Do NOT Store (Derive on Demand)

| Field                    | Why                                          |
| ------------------------ | -------------------------------------------- |
| Raw per-exchange scores  | Already in `evaluations`                     |
| Rubric criteria JSON     | Already in `rubric_dimensions`               |
| Question text            | Already snapshotted in `interview_exchanges` |
| Dimension justifications | Already in `evaluation_dimension_scores`     |

---

## Aggregation Algorithm (Conceptual)

### Step 1: Aggregate Per Exchange

```sql
SELECT
  e.interview_exchange_id,
  SUM(eds.score * rd.weight) / SUM(rd.weight) AS weighted_exchange_score
FROM evaluations e
JOIN evaluation_dimension_scores eds ON eds.evaluation_id = e.id
JOIN rubric_dimensions rd ON rd.id = eds.rubric_dimension_id
WHERE e.interview_exchange_id IN (...)
GROUP BY e.interview_exchange_id;
```

### Step 2: Map to Sections

Lookup `interview_exchanges.sequence_order` → `template_structure` section mapping.

```json
{
  "resume_analysis": [1], // exchange 1
  "topics_assessment": [2, 3, 4], // exchanges 2-4
  "coding_round": [5, 6] // exchanges 5-6
}
```

### Step 3: Apply Template Weights

```sql
SELECT
  section_name,
  SUM(exchange_score) * section_weight AS section_score
FROM section_exchange_mapping
GROUP BY section_name;
```

### Step 4: Normalize & Finalize

```sql
final_score = SUM(section_scores)
normalized_score = (final_score / max_possible_score) * 100
result_status = CASE
  WHEN normalized_score >= 80 THEN 'pass'
  WHEN normalized_score >= 60 THEN 'borderline'
  ELSE 'fail'
END
```

---

## Audit & Explanation Trail

### Question: "Why did candidate X get 72.5?"

**Answer (6 months later):**

1. Query `interview_results` → get `scoring_version`, `section_scores`
2. Query `rubric_snapshot` → see which weights were used
3. Query `template_weight_snapshot` → see section weights
4. Drill into `evaluations` → per-exchange scores
5. Drill into `evaluation_dimension_scores` → dimension justifications

All data frozen. No ambiguity.

---

## Supplementary Reports

For optional detailed analysis (proctoring risk, technical breakdown):

```sql
supplementary_reports (
  interview_submission_id bigint,
  report_type report_type,  -- technical_breakdown, proctoring_risk, etc.
  content jsonb,            -- flexible structure
  ...
);
```

**Why separate?**

- Core `interview_results` stays clean
- Reports can be regenerated without affecting scores
- Different retention policies

---

## Edge Cases Handled

### Partial Interviews

```json
{
  "result_status": "incomplete",
  "section_scores": {
    "resume_analysis": 8.5,
    "topics_assessment": 0, // not attempted
    "coding_round": null // skipped
  }
}
```

### Skipped Exchanges

- Store `null` in section_scores
- Do not penalize (unless template rules say so)
- Flag in `summary_notes`

### Proctoring Violations

- Compute base score normally
- Apply penalty multiplier
- Document in `summary_notes`

```sql
final_score = base_score * proctoring_penalty_factor
```

---

## Implementation Checklist

- [ ] Create `interview_results` table
- [ ] Create `supplementary_reports` table
- [ ] Write aggregation SQL function
- [ ] Build async scoring job
- [ ] Add re-evaluation workflow
- [ ] Implement version management
- [ ] Add audit trail API endpoint
- [ ] Test edge cases (partial, skipped, violations)

---

## 30-Second Explanation (For Interviews)

> "We store exchange-level evaluations normalized. When an interview completes, we compute the final score once using weighted aggregation, snapshot the rubric and template weights used, and store everything in `interview_results`. This ensures audit trails are immutable—if someone asks 'why this score?' six months later, we can explain confidently. Re-evaluations create new versions; we never overwrite history."

---

## References

- Main schema: [schema.sql](schema.sql)
- ERD: [erd.dsl](erd.dsl)
- Architecture review: [ARCHITECTURE-REVIEW.md](ARCHITECTURE-REVIEW.md)
