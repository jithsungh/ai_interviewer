# Proctoring Rules - Severity & Weight Assignment

## 1. Purpose

The **rules** subdirectory handles:

- Mapping event types to severity levels (low, medium, high, critical)
- Assigning base risk weights per event type
- Applying clustering multipliers (repeated events escalate severity)
- Supporting configurable, tenant-specific rule overrides
- Versioning rule changes for auditability

**Critical responsibility:** Deterministic, explainable risk weight assignment with full audit trail.

---

## 2. Responsibilities

### 2.1 Event-to-Severity Mapping

**Provides:**

- Predefined severity for each event type
- Severity levels: `low`, `medium`, `high`, `critical`

**Example mapping:**
| Event Type | Base Severity |
|--------------------------|---------------|
| tab_switch | low |
| window_blur | low |
| face_absent | medium |
| multiple_faces | high |
| multiple_voices | high |
| camera_disabled | medium |
| microphone_disabled | low |
| background_noise_spike | medium |
| device_change | low |
| screen_recording_started | info (0) |
| screen_recording_stopped | info (0) |

**Must:**

- Return consistent severity for same event type
- Support override severity rules (low → medium if repeated)
- Log severity assignment reason

---

### 2.2 Risk Weight Assignment

**Provides:**

- Base risk weight per event type
- Weight is numeric value contributing to total risk score

**Example weights:**
| Event Type | Base Weight |
|--------------------------|-------------|
| tab_switch | 0.5 |
| window_blur | 0.5 |
| face_absent | 1.5 |
| multiple_faces | 3.0 |
| multiple_voices | 3.0 |
| camera_disabled | 2.0 |
| microphone_disabled | 1.0 |
| background_noise_spike | 1.5 |
| device_change | 1.0 |
| screen_recording_started | 0.0 |
| screen_recording_stopped | 0.0 |

**Must:**

- Return numeric weight (float, >= 0.0)
- Support configurable weights (via config)
- Allow tenant-specific weight overrides

---

### 2.3 Clustering Multipliers

**Purpose:** Escalate severity/weight when events cluster in time.

**Example rules:**

1. **Tab switch clustering:**
   - Condition: 10+ `tab_switch` events in 60 seconds
   - Action: Escalate severity from `low` → `medium`, apply 1.5x weight multiplier

2. **Face absent clustering:**
   - Condition: 3+ consecutive `face_absent` events
   - Action: Escalate severity from `medium` → `high`, apply 2.0x weight multiplier

3. **Multiple faces repeated:**
   - Condition: 5+ `multiple_faces` events in 5 minutes
   - Action: Escalate severity from `high` → `critical`, apply 2.5x weight multiplier

**Must:**

- Query recent events for same submission within time window
- Apply multiplier deterministically
- Log clustering detection with count and timespan

---

### 2.4 Rule Versioning

**Must support:**

- Rule schema version (e.g., `v1.2.0`)
- Rule change audit log
- Historical rule retrieval (for event explanation)

**Use case:**

- Admin updates weight for `camera_disabled` from 2.0 → 1.5
- All new events use v1.3.0 rules
- Historical events retain v1.2.0 rule reference
- Risk score recomputation uses appropriate rule version

**Implementation:**

```python
@dataclass
class RuleVersion:
    version: str  # e.g., "v1.2.0"
    effective_date: datetime
    event_weights: dict[str, float]
    event_severities: dict[str, str]
    clustering_rules: list[ClusteringRule]
    created_by: int  # admin user_id
```

---

## 3. Rule Definition Schema

### 3.1 Base Rule

**Structure:**

```python
@dataclass
class ProctoringRule:
    """Base rule for single event type."""
    event_type: str
    base_severity: str  # low, medium, high, critical
    base_weight: float  # >= 0.0
    description: str
    rule_version: str
```

**Example:**

```python
ProctoringRule(
    event_type="tab_switch",
    base_severity="low",
    base_weight=0.5,
    description="Candidate switched browser tab during interview",
    rule_version="v1.2.0"
)
```

---

### 3.2 Clustering Rule

**Structure:**

```python
@dataclass
class ClusteringRule:
    """Rule for escalating severity based on event clustering."""
    event_type: str
    condition_type: str  # "count_in_window", "consecutive"
    threshold: int  # e.g., 10 events
    time_window_seconds: int  # e.g., 60 seconds
    escalated_severity: str  # e.g., "medium"
    weight_multiplier: float  # e.g., 1.5x
    rule_version: str
```

**Example:**

```python
ClusteringRule(
    event_type="tab_switch",
    condition_type="count_in_window",
    threshold=10,
    time_window_seconds=60,
    escalated_severity="medium",
    weight_multiplier=1.5,
    rule_version="v1.2.0"
)
```

---

## 4. Rule Application Workflow

### 4.1 Single Event Processing

**Input:** Validated event from ingestion

**Steps:**

1. Retrieve current rule version
2. Lookup base severity and weight for event_type
3. Query recent events for clustering detection
4. Apply clustering multiplier if triggered
5. Return enriched event with severity and weight

**Output:**

```python
@dataclass
class EnrichedProctoringEvent:
    # Original event fields
    submission_id: int
    organization_id: int
    event_type: str
    timestamp: datetime
    metadata: dict

    # Rule application results
    base_severity: str
    base_weight: float
    applied_severity: str  # May be escalated
    applied_weight: float  # May be multiplied
    clustering_detected: bool
    clustering_reason: Optional[str]
    rule_version: str
```

---

### 4.2 Clustering Detection

**Algorithm:**

```python
def detect_clustering(
    submission_id: int,
    event_type: str,
    current_timestamp: datetime,
    clustering_rules: list[ClusteringRule]
) -> tuple[bool, Optional[ClusteringRule]]:
    """
    Check if event triggers clustering escalation.

    Returns: (is_clustered, applied_rule)
    """
    for rule in clustering_rules:
        if rule.event_type != event_type:
            continue

        if rule.condition_type == "count_in_window":
            # Count events in time window
            window_start = current_timestamp - timedelta(seconds=rule.time_window_seconds)
            recent_events = get_events_in_window(
                submission_id, event_type, window_start, current_timestamp
            )

            if len(recent_events) >= rule.threshold:
                return (True, rule)

        elif rule.condition_type == "consecutive":
            # Check consecutive events
            recent_events = get_last_n_events(
                submission_id, event_type, n=rule.threshold
            )

            # Verify no other event types in between
            if len(recent_events) == rule.threshold:
                timestamps = [e.timestamp for e in recent_events]
                # All within threshold timespan
                if (max(timestamps) - min(timestamps)).seconds <= rule.time_window_seconds:
                    return (True, rule)

    return (False, None)
```

---

## 5. Default Rule Configuration

### 5.1 Base Rules (v1.0.0)

**Low severity events (weight 0.5 - 1.0):**

```python
DEFAULT_RULES = [
    ProctoringRule("tab_switch", "low", 0.5, "Tab switch detected"),
    ProctoringRule("window_blur", "low", 0.5, "Window lost focus"),
    ProctoringRule("window_focus_lost", "low", 0.5, "Window minimized"),
    ProctoringRule("microphone_disabled", "low", 1.0, "Microphone muted"),
    ProctoringRule("device_change", "low", 1.0, "Device changed"),
]
```

**Medium severity events (weight 1.5 - 2.0):**

```python
DEFAULT_RULES += [
    ProctoringRule("face_absent", "medium", 1.5, "Face not detected in frame"),
    ProctoringRule("camera_disabled", "medium", 2.0, "Camera turned off"),
    ProctoringRule("background_noise_spike", "medium", 1.5, "Background noise spike"),
]
```

**High severity events (weight 3.0):**

```python
DEFAULT_RULES += [
    ProctoringRule("multiple_faces", "high", 3.0, "Multiple faces detected"),
    ProctoringRule("multiple_voices", "high", 3.0, "Multiple voices detected"),
]
```

**Info events (weight 0.0):**

```python
DEFAULT_RULES += [
    ProctoringRule("screen_recording_started", "info", 0.0, "Screen recording started"),
    ProctoringRule("screen_recording_stopped", "info", 0.0, "Screen recording stopped"),
]
```

---

### 5.2 Clustering Rules (v1.0.0)

**Tab switch clustering:**

```python
ClusteringRule(
    event_type="tab_switch",
    condition_type="count_in_window",
    threshold=10,
    time_window_seconds=60,
    escalated_severity="medium",
    weight_multiplier=1.5,
    rule_version="v1.0.0"
)
```

**Face absent clustering:**

```python
ClusteringRule(
    event_type="face_absent",
    condition_type="consecutive",
    threshold=3,
    time_window_seconds=30,
    escalated_severity="high",
    weight_multiplier=2.0,
    rule_version="v1.0.0"
)
```

**Multiple faces clustering:**

```python
ClusteringRule(
    event_type="multiple_faces",
    condition_type="count_in_window",
    threshold=5,
    time_window_seconds=300,
    escalated_severity="critical",
    weight_multiplier=2.5,
    rule_version="v1.0.0"
)
```

---

## 6. Configuration Management

### 6.1 Rule Storage

**Must support:**

- Load rules from config file (YAML/JSON)
- Load rules from database (admin-configured)
- Tenant-specific rule overrides

**Priority:**

1. Tenant-specific rules (if configured)
2. Organization-level rules
3. Global default rules

---

### 6.2 Configuration Format

**YAML example:**

```yaml
rule_version: v1.2.0
effective_date: 2026-02-14T00:00:00Z

base_rules:
  tab_switch:
    severity: low
    weight: 0.5
  multiple_faces:
    severity: high
    weight: 3.0

clustering_rules:
  - event_type: tab_switch
    condition: count_in_window
    threshold: 10
    time_window_seconds: 60
    escalated_severity: medium
    weight_multiplier: 1.5
```

---

### 6.3 Rule Update Workflow

**Admin updates rule:**

1. Admin modifies weight via admin UI
2. System creates new rule version (e.g., v1.2.0 → v1.3.0)
3. New version becomes effective immediately for new events
4. Historical events retain reference to old version
5. Audit log records change (admin_id, old_value, new_value, timestamp)

**Example audit log entry:**

```json
{
  "audit_id": 12345,
  "rule_version_old": "v1.2.0",
  "rule_version_new": "v1.3.0",
  "changes": [
    {
      "event_type": "camera_disabled",
      "field": "base_weight",
      "old_value": 2.0,
      "new_value": 1.5
    }
  ],
  "changed_by": 42, // admin user_id
  "changed_at": "2026-02-14T10:30:00Z",
  "reason": "Reduced severity after false positive analysis"
}
```

---

## 7. Tenant-Specific Overrides

### 7.1 Use Case

**Scenario:** Organization A wants stricter tab switch rules.

**Configuration:**

```python
tenant_override = {
    "organization_id": 123,
    "rule_overrides": {
        "tab_switch": {
            "base_weight": 1.0,  # Default: 0.5
            "clustering_threshold": 5  # Default: 10
        }
    }
}
```

**Application:**

1. Event received for submission in Org 123
2. Check tenant overrides first
3. If override exists, use override weight
4. If not, fall back to global rule

---

### 7.2 Storage

**Table:** `proctoring_rule_overrides`

**Schema:**

```sql
CREATE TABLE proctoring_rule_overrides (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    event_type VARCHAR(50) NOT NULL,
    override_severity VARCHAR(20),
    override_weight NUMERIC(5, 2),
    override_clustering_threshold INTEGER,
    override_clustering_multiplier NUMERIC(5, 2),
    created_by INTEGER REFERENCES admins(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(organization_id, event_type)
);
```

---

## 8. Rule Application Service

### 8.1 Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

class RuleService(ABC):
    """Abstract interface for rule application."""

    @abstractmethod
    def apply_rules(
        self,
        submission_id: int,
        organization_id: int,
        event_type: str,
        timestamp: datetime
    ) -> RuleApplicationResult:
        """
        Apply severity and weight rules to event.

        Returns enriched event with severity, weight, clustering info.
        """
        pass

    @abstractmethod
    def get_current_rule_version(self, organization_id: int) -> str:
        """Get effective rule version for organization."""
        pass
```

---

### 8.2 Implementation Example

```python
class ProctoringRuleService(RuleService):
    """Concrete implementation of rule application."""

    def __init__(self, db: Session, redis: Redis, config: ProctoringConfig):
        self.db = db
        self.redis = redis
        self.config = config
        self._load_rules()

    def apply_rules(
        self,
        submission_id: int,
        organization_id: int,
        event_type: str,
        timestamp: datetime
    ) -> RuleApplicationResult:
        """Apply rules with clustering detection."""

        # Get base rule (with tenant override check)
        base_rule = self._get_rule(organization_id, event_type)

        # Check clustering
        is_clustered, clustering_rule = self._detect_clustering(
            submission_id, event_type, timestamp
        )

        # Apply multiplier if clustered
        if is_clustered:
            applied_severity = clustering_rule.escalated_severity
            applied_weight = base_rule.base_weight * clustering_rule.weight_multiplier
            clustering_reason = (
                f"{clustering_rule.threshold} events in "
                f"{clustering_rule.time_window_seconds}s"
            )
        else:
            applied_severity = base_rule.base_severity
            applied_weight = base_rule.base_weight
            clustering_reason = None

        return RuleApplicationResult(
            base_severity=base_rule.base_severity,
            base_weight=base_rule.base_weight,
            applied_severity=applied_severity,
            applied_weight=applied_weight,
            clustering_detected=is_clustered,
            clustering_reason=clustering_reason,
            rule_version=base_rule.rule_version
        )

    def _get_rule(self, organization_id: int, event_type: str) -> ProctoringRule:
        """Get rule with tenant override check."""

        # Check tenant override
        override = self.db.query(ProctoringRuleOverride).filter_by(
            organization_id=organization_id,
            event_type=event_type
        ).first()

        if override:
            return ProctoringRule(
                event_type=event_type,
                base_severity=override.override_severity or self._default_rules[event_type].base_severity,
                base_weight=override.override_weight or self._default_rules[event_type].base_weight,
                description=self._default_rules[event_type].description,
                rule_version=self._current_version
            )

        # Fall back to default
        return self._default_rules[event_type]

    def _detect_clustering(
        self,
        submission_id: int,
        event_type: str,
        current_timestamp: datetime
    ) -> tuple[bool, Optional[ClusteringRule]]:
        """Detect if event triggers clustering escalation."""

        for rule in self._clustering_rules:
            if rule.event_type != event_type:
                continue

            if rule.condition_type == "count_in_window":
                window_start = current_timestamp - timedelta(seconds=rule.time_window_seconds)

                # Query recent events (use Redis for speed)
                recent_count = self._count_events_in_window(
                    submission_id, event_type, window_start, current_timestamp
                )

                if recent_count >= rule.threshold:
                    return (True, rule)

        return (False, None)
```

---

## 9. Observability

### 9.1 Metrics

**Must expose:**

- `proctoring_rules_applied_total` (counter with labels: event_type, severity) - Total rules applied
- `proctoring_clustering_detected_total` (counter with label: event_type) - Clustering escalations
- `proctoring_rule_lookup_duration_seconds` (histogram) - Rule lookup latency

---

### 9.2 Logging

**Must log (INFO level):**

- Rule applied (event_type, base_severity, base_weight, rule_version)
- Clustering detected (event_type, count, timespan, escalated_severity)
- Tenant override used (organization_id, event_type, override_values)

**Must log (WARN level):**

- Unknown event type (fallback to default rule)
- Rule version mismatch (expected vs actual)

---

## 10. Testing Requirements

### 10.1 Unit Tests

1. **Base rule lookup:** Event type → correct severity and weight
2. **Tenant override:** Org with override → custom weight applied
3. **Clustering detection:** 10 tab switches in 60s → clustered = true
4. **Clustering multiplier:** Clustered event → weight × 1.5
5. **Rule versioning:** Historical event → old rule version retrieved

---

### 10.2 Integration Tests

1. **End-to-end:** Event ingested → rules applied → severity/weight stored
2. **Tenant isolation:** Org 1 override does not affect Org 2
3. **Rule update:** Admin changes weight → new events use new weight
4. **Clustering across events:** 5 tab switches + 5 more → clustering detected on 6th

---

## 11. Critical Risks

1. **Rule drift:** Rule changes without versioning → historical risk scores non-reproducible
2. **Clustering false positives:** Legitimate tab switches (e.g., checking docs) → over-escalation
3. **Tenant override collision:** Multiple admins update same rule → last write wins (race condition)
4. **Performance degradation:** Clustering detection queries slow under load → event processing delayed
5. **Missing rule:** New event type added without rule → fallback to default (may be inappropriate)

---

## 12. Acceptance Criteria

**Rules module is complete when:**

✅ Base rules defined for all event types
✅ Severity and weight assignment deterministic
✅ Clustering detection working (count_in_window + consecutive)
✅ Clustering multipliers applied correctly
✅ Tenant-specific overrides supported
✅ Rule versioning implemented with audit log
✅ Rule service interface implemented
✅ Configuration loading from YAML/JSON
✅ Metrics exposed (rules applied, clustering detected)
✅ Logging complete (INFO + WARN levels)
✅ All tests passing (unit + integration)

---

**End of Proctoring Rules Requirements**
