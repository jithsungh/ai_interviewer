# Evaluation Snapshots - Audit-Safe Context Freezing

## 1. Purpose

The **Snapshots** layer is responsible for:

- Capturing rubric configuration at evaluation time
- Capturing template weights at evaluation time
- Capturing scoring model metadata
- Ensuring reproducibility of scoring
- Providing audit-safe context for historical review

**Critical responsibility:** This is the **audit guarantee mechanism**. It must:

- Freeze all scoring context (rubric, template, model)
- Enable reproduction of exact scores weeks/months later
- Prevent "configuration drift" from breaking audit trail
- Support compliance and legal requirements

---

## 2. Why Snapshots Matter

### Problem: Configuration Drift

**Without snapshots:**

1. Interview evaluated with Rubric v1 (5 dimensions)
2. Admin updates rubric to v2 (8 dimensions)
3. Later, someone reviews interview result
4. **Question:** "How was this scored? What rubric was used?"
5. **Problem:** Cannot reproduce original score (rubric changed)

**With snapshots:**

1. Evaluation stores rubric_snapshot (v1 frozen in JSONB)
2. Rubric updated to v2, but snapshot unchanged
3. Later review retrieves snapshot
4. **Result:** Exact scoring context preserved, reproducible

---

## 3. Snapshot Types

### 1️⃣ Rubric Snapshot

**What to capture:**

- rubric_id
- rubric_name
- rubric_description
- dimensions: List of:
  - dimension_id
  - dimension_name
  - weight
  - max_score
  - description
  - scoring_criteria

**Stored in:** `interview_results.rubric_snapshot` (JSONB)

---

### 2️⃣ Template Weight Snapshot

**What to capture:**

- template_id
- section_weights: Dict of `{section_name: weight}`
  - Example: `{"resume": 10, "behavioral": 30, "coding": 60}`

**Stored in:** `interview_results.template_weight_snapshot` (JSONB)

---

### 3️⃣ Model Snapshot

**What to capture:**

- model_id (e.g., "gpt-4-turbo")
- scoring_version (e.g., "1.0")
- evaluator_type (ai | human | hybrid)
- evaluation_timestamp

**Stored in:** `evaluations.model_id`, `evaluations.scoring_version`, `evaluations.evaluator_type`

---

## 4. Rubric Snapshot Schema

### JSON Structure

```json
{
  "rubric_id": 5,
  "rubric_name": "Software Engineer L3",
  "rubric_description": "Rubric for mid-level software engineer evaluation",
  "dimensions": [
    {
      "dimension_id": 1,
      "dimension_name": "Accuracy",
      "weight": 40,
      "max_score": 5.0,
      "description": "Correctness and completeness of answer",
      "scoring_criteria": "5 = Fully correct with all edge cases\n4 = Mostly correct with minor gaps\n3 = Partially correct\n2 = Major gaps\n1 = Incorrect"
    },
    {
      "dimension_id": 2,
      "dimension_name": "Clarity",
      "weight": 30,
      "max_score": 5.0,
      "description": "Communication clarity and structure",
      "scoring_criteria": "..."
    },
    {
      "dimension_id": 3,
      "dimension_name": "Efficiency",
      "weight": 20,
      "max_score": 5.0,
      "description": "Time and space complexity awareness",
      "scoring_criteria": "..."
    },
    {
      "dimension_id": 4,
      "dimension_name": "Confidence",
      "weight": 10,
      "max_score": 5.0,
      "description": "Confidence and composure during answer",
      "scoring_criteria": "..."
    }
  ],
  "snapshot_timestamp": "2026-02-14T11:00:00Z"
}
```

### Pydantic Schema

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DimensionSnapshot(BaseModel):
    dimension_id: int
    dimension_name: str
    weight: int
    max_score: float
    description: str
    scoring_criteria: Optional[str]

class RubricSnapshot(BaseModel):
    rubric_id: int
    rubric_name: str
    rubric_description: Optional[str]
    dimensions: List[DimensionSnapshot]
    snapshot_timestamp: datetime
```

---

## 5. Template Weight Snapshot Schema

### JSON Structure

```json
{
  "template_id": 3,
  "template_name": "Full Stack Engineer Interview",
  "section_weights": {
    "resume": 10,
    "behavioral": 30,
    "coding": 60
  },
  "snapshot_timestamp": "2026-02-14T11:00:00Z"
}
```

### Pydantic Schema

```python
from typing import Dict

class TemplateWeightSnapshot(BaseModel):
    template_id: int
    template_name: str
    section_weights: Dict[str, int]
    snapshot_timestamp: datetime
```

---

## 6. Snapshot Creation

### When to Create

**Rubric Snapshot:**

- Created during **interview result finalization**
- One snapshot per interview (stored in `interview_results.rubric_snapshot`)

**Template Weight Snapshot:**

- Created during **interview result finalization**
- One snapshot per interview (stored in `interview_results.template_weight_snapshot`)

**Model Snapshot:**

- Created per **evaluation** (stored in `evaluations` table columns)

---

### Function Signatures

#### Create Rubric Snapshot

```python
def create_rubric_snapshot(
    rubric_id: int,
    dimensions: List[RubricDimensionDTO]
) -> dict:
    """
    Create rubric snapshot for audit trail.

    Args:
        rubric_id: Rubric ID
        dimensions: List of rubric dimensions with metadata

    Returns:
        dict (serializable to JSONB)
    """
    rubric = fetch_rubric(rubric_id)

    snapshot = RubricSnapshot(
        rubric_id=rubric.id,
        rubric_name=rubric.name,
        rubric_description=rubric.description,
        dimensions=[
            DimensionSnapshot(
                dimension_id=d.rubric_dimension_id,
                dimension_name=d.dimension_name,
                weight=d.weight,
                max_score=d.max_score,
                description=d.description,
                scoring_criteria=d.scoring_criteria
            )
            for d in dimensions
        ],
        snapshot_timestamp=datetime.utcnow()
    )

    return snapshot.model_dump()
```

#### Create Template Weight Snapshot

```python
def create_template_weight_snapshot(
    template_id: int,
    section_weights: Dict[str, int]
) -> dict:
    """
    Create template weight snapshot for audit trail.

    Args:
        template_id: Template ID
        section_weights: Section weights {'resume': 10, ...}

    Returns:
        dict (serializable to JSONB)
    """
    template = fetch_template(template_id)

    snapshot = TemplateWeightSnapshot(
        template_id=template.id,
        template_name=template.name,
        section_weights=section_weights,
        snapshot_timestamp=datetime.utcnow()
    )

    return snapshot.model_dump()
```

---

## 7. Snapshot Retrieval

### Purpose

Retrieve frozen context for audit review or re-calculation.

### Function Signatures

#### Retrieve Rubric Snapshot

```python
def retrieve_rubric_snapshot(result_id: int) -> RubricSnapshot:
    """
    Retrieve rubric snapshot from interview result.

    Args:
        result_id: Interview result ID

    Returns:
        RubricSnapshot

    Raises:
        ResultNotFound: Result does not exist
    """
    result = fetch_interview_result(result_id)
    return RubricSnapshot(**result.rubric_snapshot)
```

#### Retrieve Template Weight Snapshot

```python
def retrieve_template_weight_snapshot(result_id: int) -> TemplateWeightSnapshot:
    """
    Retrieve template weight snapshot from interview result.

    Args:
        result_id: Interview result ID

    Returns:
        TemplateWeightSnapshot
    """
    result = fetch_interview_result(result_id)
    return TemplateWeightSnapshot(**result.template_weight_snapshot)
```

---

## 8. Snapshot Validation

### Purpose

Ensure snapshot integrity (no corruption, all required fields present).

### Validation Rules

**Rubric Snapshot:**

1. rubric_id present and > 0
2. dimensions list not empty
3. Each dimension has: id, name, weight, max_score
4. snapshot_timestamp present

**Template Weight Snapshot:**

1. template_id present and > 0
2. section_weights not empty
3. All weights > 0
4. snapshot_timestamp present

### Function Signature

```python
from typing import Optional

class SnapshotValidationError(Exception):
    pass

def validate_rubric_snapshot(snapshot: dict) -> Optional[str]:
    """
    Validate rubric snapshot structure.

    Returns:
        None if valid, error message if invalid
    """
    if "rubric_id" not in snapshot or snapshot["rubric_id"] <= 0:
        return "Missing or invalid rubric_id"

    if "dimensions" not in snapshot or len(snapshot["dimensions"]) == 0:
        return "Missing or empty dimensions"

    for dimension in snapshot["dimensions"]:
        required_fields = ["dimension_id", "dimension_name", "weight", "max_score"]
        for field in required_fields:
            if field not in dimension:
                return f"Dimension missing field: {field}"

    if "snapshot_timestamp" not in snapshot:
        return "Missing snapshot_timestamp"

    return None

def validate_template_weight_snapshot(snapshot: dict) -> Optional[str]:
    """
    Validate template weight snapshot structure.

    Returns:
        None if valid, error message if invalid
    """
    if "template_id" not in snapshot or snapshot["template_id"] <= 0:
        return "Missing or invalid template_id"

    if "section_weights" not in snapshot or len(snapshot["section_weights"]) == 0:
        return "Missing or empty section_weights"

    for section, weight in snapshot["section_weights"].items():
        if not isinstance(weight, int) or weight < 0:
            return f"Invalid weight for section {section}: {weight}"

    if "snapshot_timestamp" not in snapshot:
        return "Missing snapshot_timestamp"

    return None
```

---

## 9. Snapshot Immutability

### Guarantees

**Must enforce:**

1. Snapshots NEVER modified after creation
2. Snapshots stored in JSONB (immutable column type)
3. No UPDATE statements on snapshot columns
4. New result version creates new snapshot (no reuse)

**Forbidden:**

- `UPDATE interview_results SET rubric_snapshot = ...`
- `UPDATE interview_results SET template_weight_snapshot = ...`

**Allowed:**

- `INSERT INTO interview_results (..., rubric_snapshot, template_weight_snapshot) VALUES (...)`

---

## 10. Snapshot Comparison

### Purpose

Compare current configuration with historical snapshot (detect drift).

### Use Cases

1. **Audit review:** "How has rubric changed since this interview?"
2. **Debugging:** "Why is current score different from historical?"
3. **Compliance:** "Prove scoring was consistent with policy"

### Function Signature

```python
from typing import List

class SnapshotDiff(BaseModel):
    field: str
    old_value: Any
    new_value: Any
    change_type: str  # 'added' | 'removed' | 'modified'

def compare_rubric_snapshots(
    snapshot_a: RubricSnapshot,
    snapshot_b: RubricSnapshot
) -> List[SnapshotDiff]:
    """
    Compare two rubric snapshots.

    Returns:
        List of differences
    """
    diffs = []

    # Compare dimensions
    dims_a = {d.dimension_id: d for d in snapshot_a.dimensions}
    dims_b = {d.dimension_id: d for d in snapshot_b.dimensions}

    # Added dimensions
    for dim_id in dims_b.keys() - dims_a.keys():
        diffs.append(SnapshotDiff(
            field=f"dimension_{dim_id}",
            old_value=None,
            new_value=dims_b[dim_id].dimension_name,
            change_type="added"
        ))

    # Removed dimensions
    for dim_id in dims_a.keys() - dims_b.keys():
        diffs.append(SnapshotDiff(
            field=f"dimension_{dim_id}",
            old_value=dims_a[dim_id].dimension_name,
            new_value=None,
            change_type="removed"
        ))

    # Modified dimensions
    for dim_id in dims_a.keys() & dims_b.keys():
        dim_a = dims_a[dim_id]
        dim_b = dims_b[dim_id]

        if dim_a.weight != dim_b.weight:
            diffs.append(SnapshotDiff(
                field=f"dimension_{dim_id}.weight",
                old_value=dim_a.weight,
                new_value=dim_b.weight,
                change_type="modified"
            ))

        if dim_a.max_score != dim_b.max_score:
            diffs.append(SnapshotDiff(
                field=f"dimension_{dim_id}.max_score",
                old_value=dim_a.max_score,
                new_value=dim_b.max_score,
                change_type="modified"
            ))

    return diffs
```

---

## 11. Snapshot Storage Optimization

### Considerations

**JSONB advantages:**

- Native PostgreSQL support
- Indexable (if needed)
- Queryable with JSON operators
- Immutable by design

**Size concerns:**

- Each snapshot ~1-5 KB (typical rubric)
- 10,000 interviews = 10-50 MB (negligible)
- No compression needed

**Retention:**

- Keep snapshots forever (audit requirement)
- No deletion

---

## 12. Edge Cases

### 1. Rubric Deleted After Interview

**Scenario:** Rubric deleted from `rubrics` table, but snapshot preserved.

**Handling:**

- Snapshot remains in `interview_results.rubric_snapshot`
- Audit trail intact
- Warning logged: "Rubric 5 deleted, but snapshot preserved"

---

### 2. Snapshot Corruption

**Scenario:** JSONB column corrupted (invalid JSON).

**Handling:**

- Validation on retrieval detects corruption
- Raise `SnapshotCorruptionError`
- Log critical alert for investigation

---

### 3. Template Weight Sum Changed

**Scenario:** Old template: `{resume: 10, behavioral: 30, coding: 60}` (sum=100).  
New template: `{resume: 20, behavioral: 40, coding: 60}` (sum=120).

**Handling:**

- Snapshot preserves old weights (sum=100)
- Normalization uses old max_possible calculation
- Reproducibility guaranteed

---

### 4. Dimension Removed from Rubric

**Scenario:** Rubric v1 has "Confidence" dimension. Rubric v2 removes it.

**Handling:**

- Snapshot preserves "Confidence" with weight 10
- Historical score reproducible
- Current rubric does not include "Confidence" (new interviews)

---

## 13. API Exposure

### Endpoint: GET /api/evaluation/results/{result_id}/snapshot

**Purpose:** Fetch frozen snapshots for audit review.

#### Response

```json
{
  "result_id": 789,
  "interview_id": 100,
  "rubric_snapshot": {
    "rubric_id": 5,
    "rubric_name": "Software Engineer L3",
    "dimensions": [...]
  },
  "template_weight_snapshot": {
    "template_id": 3,
    "template_name": "Full Stack Engineer Interview",
    "section_weights": {"resume": 10, "behavioral": 30, "coding": 60}
  },
  "current_rubric_id": 7,
  "current_template_id": 3,
  "configuration_changed": true
}
```

**Authorization:** Admin only, or candidate for own interview.

---

## 14. Testing Requirements

### Unit Tests

1. **Snapshot creation:** Valid rubric/template → valid snapshot
2. **Snapshot validation:** Missing fields → error
3. **Snapshot retrieval:** Deserialize JSONB → Pydantic model
4. **Snapshot comparison:** Detect added/removed/modified dimensions

### Integration Tests

1. **End-to-end:** Interview finalized → snapshots stored
2. **Rubric updated:** Old snapshot unchanged, new interviews use new rubric
3. **Snapshot retrieval:** API returns correct snapshot

### Edge Case Tests

1. **Rubric deleted:** Snapshot preserved
2. **JSONB corruption:** Validation detects and raises error
3. **Dimension removed:** Snapshot preserves old dimension
4. **Empty dimensions:** Validation rejects

---

## 15. Critical Risks

1. **No snapshots:** Configuration drift breaks audit trail
2. **Mutable snapshots:** UPDATE operations corrupt history
3. **No validation:** Corrupted snapshots cause deserialization errors
4. **Dynamic rubric fetch:** Non-reproducible scoring
5. **Snapshot deletion:** Audit trail destroyed

---

## 16. Compliance & Legal

### Audit Requirements

**Must support:**

1. Reproduce exact score using historical context
2. Prove scoring was consistent with policy at time of evaluation
3. Demonstrate no retroactive changes to scoring
4. Provide evidence of rubric/template used

**Snapshot guarantees:**

- Immutable
- Timestamped
- Complete (all dimensions, weights, criteria)
- Versioned (linked to result_id)

---

## 17. Future Enhancements

1. **Snapshot versioning:** Track rubric version numbers explicitly
2. **Snapshot diffing API:** Compare current vs historical in UI
3. **Snapshot export:** Download as JSON for external audit
4. **Snapshot compression:** Compress large snapshots (>10 KB)
5. **Snapshot search:** Query interviews by historical rubric version

---

**End of Evaluation Snapshots Requirements**
