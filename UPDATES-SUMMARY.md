# 🎯 Architectural Update Summary: Intent Classification & Clarification System

**Date:** February 17, 2026  
**Status:** ✅ COMPLETE  
**Scope:** Formal specification of high-integrity clarification architecture across 6+ modules

---

## 📋 Changes Made

### 1. Core Architecture Document (NEW)

**File:** [docs/CLARIFICATIONS-ARCHITECTURE.md](../docs/CLARIFICATIONS-ARCHITECTURE.md)

**Purpose:** Single source of truth for the entire clarification system.

**Contents:**
- Executive summary (key decisions)
- 5-layer architecture overview
- Data flow example with code
- Fairness & audit trail design
- Implementation checklist
- Risk mitigation strategies
- Cross-module references

**Why:** Ensures all teams understand the unified vision before implementation.

---

### 2. Interview Exchanges Module (MAJOR UPDATE)

**File:** [app/interview/exchanges/REQUIREMENTS.md](../app/interview/exchanges/REQUIREMENTS.md)

**New Sections:**

#### A. Intent Classification Taxonomy (§2)

- **Intent types:** ANSWER, CLARIFICATION, REPEAT, POST_ANSWER, INVALID, INCOMPLETE, UNKNOWN
- **Classification algorithm:** Rule-based or temperature=0 LLM
- **Conservative default:** Ambiguous → treat as ANSWER
- **Critical rule:** Classification runs FIRST (immutable)
- **Example classifications** for each intent type

**Code Contract:**
```python
@dataclass
class UtteranceIntentClassification:
    intent: Literal[ANSWER | CLARIFICATION | REPEAT | POST_ANSWER | INVALID | INCOMPLETE | UNKNOWN]
    confidence: float
    contains_solution_attempt: bool
    semantic_level: Literal[none | surface | deep]
```

#### B. Question State Machine with Clarifications (§3)

- **State diagram:** ASKED → WAITING_INPUT → (CLARIFICATION_REQUESTED ×3 max) → ANSWER_SUBMITTED → EVALUATED → NEXT_QUESTION
- **Extended interview_exchanges table:**
  - `clarification_count: INTEGER (0-3)`
  - `clarification_limit_exceeded: BOOLEAN`
  - `clarification_exchange_ids: INTEGER[]`
  - `intent_sequence: JSONB` (all intents in order)
  - `final_intent: VARCHAR(50)` + confidence

**ExchangeStateSnapshot dataclass:** Tracks current state through lifecycle.

#### C. Clarification Policy (§4)

- **Max 3 clarifications per question:** Hard limit, no exceptions
- **Auto-skip trigger:** When count >= 3, transition to NEXT_QUESTION automatically
- **What LLM can do:** Rephrase, define terms, restate constraints, 1 abstract analogy max
- **What LLM MUST NEVER do:** Algorithm suggestions, data structures, hints, validation, encouragement
- **Clarification LLM request template** with strict constraints dict
- **Policy validator** with word count checks and prohibition pattern matching

#### D. Clarification Audit Logging (§5)

```json
{
  "question_id": 101,
  "exchange_id": 5001,
  "submission_id": 1000,
  "clarification_count": 2,
  "hint_given": false,
  "final_intent_sequence": [
    {"intent": "CLARIFICATION", "confidence": 0.95, "timestamp_ms": 1000},
    {"intent": "CLARIFICATION", "confidence": 0.92, "timestamp_ms": 3500},
    {"intent": "ANSWER", "confidence": 0.88, "timestamp_ms": 8000}
  ]
}
```

#### E. Voice-Specific ASR Risk Mitigation (§6)

- ASR confidence threshold (0.70)
- If below threshold: Request repeat
- Avoid misclassification from transcription errors
- Log ASR confidence immutably

---

### 3. Audio Analysis Module (NEW SECTION)

**File:** [app/audio/analysis/REQUIREMENTS.md](../app/audio/analysis/REQUIREMENTS.md)

**New Section:** Intent Classification (§5a)

**Purpose:** Classify candidate utterance intention in real-time.

**Input Contract:**
```python
@dataclass
class IntentClassificationRequest:
    transcript: str
    confidence_score: float
    previous_submissions: int = 0
    question_context: Optional[str] = None
```

**Output Contract:**
```python
@dataclass
class IntentClassificationResult:
    intent: Literal[ANSWER | CLARIFICATION | REPEAT | POST_ANSWER | INVALID | INCOMPLETE | UNKNOWN]
    confidence: float
    contains_solution_attempt: bool
    semantic_depth: Literal[none | surface | deep]
    low_asr_confidence_warning: bool
```

**Algorithm Implementation:**
- 6-step deterministic classifier
- Solution keyword detection
- Clarification keyword detection
- Repeat request detection
- Silent/empty checks
- Immutable logging

**ASR Confidence Handling:**
- Threshold: 0.70
- Below threshold → INVALID (ask repeat)

**Integration Point:**
```python
# In audio.ingestion:
transcript = await transcription_service.transcribe(audio_bytes)
intent = await intent_classifier.classify(IntentClassificationRequest(...))
log_intent_classification(intent)  # ← IMMUTABLE FIRST
await orchestration_service.handle_candidate_input(intent)
```

**Constraints Added** (§6):
- Intent classification MUST run first
- No business logic before classification
- Immutable logging required
- No exchange creation until intent=ANSWER

---

### 4. Interview Orchestration Module (NEW SECTION)

**File:** [app/interview/orchestration/REQUIREMENTS.md](../app/interview/orchestration/REQUIREMENTS.md)

**New Section 3a:** Clarification Coordination (Strict Bounds)

**Purpose:** Orchestrate clarification workflow with max 3 hard limit.

**State Machine Diagram:**
```
WAITING_INPUT (clarif_count=0)
    ↓ [CLARIFICATION detected]
    ↓
LLM provides clarification (<120 words)
    ↓
clarif_count = 1
Replay question
    ↓
Go back to WAITING_INPUT
    ↓
[If clarif_count >= 3]: Auto-skip (no reopening)
```

**Handler: handle_clarification_request()**

Steps:
1. Check `clarification_count < 3`
2. If `>= 3`: Auto-skip, log CLARIFICATION_LIMIT_EXCEEDED, return neutral message
3. If `< 3`: Call LLM with strict constraints
4. Validate response against policy
5. Log clarification immutably
6. Increment counter
7. Return clarification + replay instruction

**LLM Call with Strict Constraints:**
```python
CLARIFICATION_SYSTEM_PROMPT_CONSTRAINTS = {
    "MAX_WORDS": 120,
    "ALLOW_ANALOGY": True,
    "ANALOGY_COUNT": 1,
    "ALLOW_HINT": False,
    "PROHIBITIONS": [...list of forbidden words...]
}
```

**New Section 3b:** Intent Classification → State Machine Integration

```python
async def handle_candidate_utterance(...):
    # Step 1: Classify intent (FIRST)
    intent = await intent_classifier.classify(...)
    
    # Step 2: Log intent (immutably)
    log_intent_classification(intent)
    
    # Step 3: Route based on intent
    if intent.intent == "INVALID":
        return request_repeat(asr_confidence)
    elif intent.intent == "REPEAT":
        return replay_question(submission_id)
    elif intent.intent == "CLARIFICATION":
        return await handle_clarification_request(...)
    elif intent.intent == "INCOMPLETE":
        return wait_for_more_input(submission_id)
    elif intent.intent == "ANSWER":
        return process_answer_submission(submission_id, transcript)
    elif intent.intent == "POST_ANSWER":
        return {"action": "reject", "message": "Answer recorded..."}
```

---

### 5. Interview Persistence Module (NEW SECTION)

**File:** [app/interview/persistence/REQUIREMENTS.md](../app/interview/persistence/REQUIREMENTS.md)

**New Section 2a:** Clarification Tracking in Submissions

**Extended interview_submissions Schema:**
```sql
-- ⭐ CLARIFICATION FAIRNESS TRACKING
total_clarifications_requested INTEGER NOT NULL DEFAULT 0
total_clarifications_granted INTEGER NOT NULL DEFAULT 0
total_auto_skips_due_to_clarification INTEGER NOT NULL DEFAULT 0
clarification_audit_log JSONB NOT NULL DEFAULT '[]'::JSONB
```

**ClarificationAuditEntry Dataclass:**
```python
@dataclass
class ClarificationAuditEntry:
    exchange_sequence: int
    question_id: int
    clarification_number: int
    candidate_request: str
    llm_response: str
    timestamp: datetime
    intent_classification: UtteranceIntentClassification
    auto_limit_exceeded: bool
```

**Purpose:** Enable fairness analysis & bias detection:
- Compare clarification counts across similar candidates
- Detect if some candidates consistently get more clarifications
- Support candidate appeals ("I got auto-skipped unfairly")

---

### 6. AI LLM Module (MAJOR NEW SECTION)

**File:** [app/ai/llm/REQUIREMENTS.md](../app/ai/llm/REQUIREMENTS.md)

**New Section 4:** Clarification Prompt Contract (Strict Mode)

**Clarification System Prompt Template:**
```
YOU MAY:
✓ Rephrase the question
✓ Define ambiguous terms
✓ Clarify constraints
✓ Ask candidate to clarify THEIR understanding

YOU MAY RARELY:
~ Provide ONE abstract analogy per question
  (must NOT show solution structure)

YOU MUST NEVER:
✗ Suggest algorithms
✗ Suggest data structures
✗ Describe steps or approach
✗ Give hints
✗ Validate attempts ("that's right")
✗ Use encouraging language
✗ Describe the answer
✗ Provide code examples
```

**ClarificationRequestContract:**
```python
@dataclass
class ClarificationRequestContract:
    submission_id: int
    exchange_sequence: int
    question_id: int
    original_question: str
    candidate_clarification_request: str
    clarification_number: int  # 1, 2, or 3
    constraints: ClarificationConstraints
    timestamp: datetime
    asr_confidence: Optional[float] = None
```

**ClarificationResponseContract:**
```python
@dataclass
class ClarificationResponseContract:
    clarification_text: str
    word_count: int
    violates_policy: bool
    violation_reason: Optional[str] = None
    contains_analogy: bool = False
    contains_hint: bool = False
    model_used: str
    temperature_used: float
    telemetry: Optional[dict] = None
```

**ClarificationValidator Class:**
```python
class ClarificationValidator:
    """Validate response against policy."""
    PROHIBITED_PATTERNS: Dict[str, str]  # regex patterns
    MAX_WORDS: int = 120
    
    def validate(response, constraints) -> Tuple[bool, Optional[str]]:
        # Check word count
        # Check prohibited patterns
        # Check prohibited words
        # Check hint/analogy counts
```

**Critical: Temperature = 0**

```python
async def generate_clarification(...) -> ClarificationResponseContract:
    response = await llm_provider.generate_text(
        ...
        temperature=0.0,  # ✅ DETERMINISTIC (not 0.7, not 1.0)
        ...
    )
    
    # Validate immediately
    is_valid, reason = validator.validate(response, constraints)
    if not is_valid:
        return safe_fallback("I can't provide that clarification...")
    return response
```

**Audit Logging:**
```python
def log_clarification(request, response) -> None:
    audit_entry = {
        "event_type": "clarification",
        "submission_id": request.submission_id,
        "exchange_sequence": request.exchange_sequence,
        "question_id": request.question_id,
        "clarification_number": request.clarification_number,
        "candidate_request": request.candidate_clarification_request,
        "llm_response": response.clarification_text,
        "violates_policy": response.violates_policy,
        "word_count": response.word_count,
        "model": response.model_used,
        "temperature": response.temperature_used,
        "timestamp": datetime.utcnow().isoformat()
    }
    audit_log.append(audit_entry)
```

**Section numbering updated:** 4→5→6→7 (shifted from 4→5→...)

---

### 7. Cross-Module References (NEW)

Added reference to master architecture document in:

- ✅ [app/interview/exchanges/REQUIREMENTS.md](../app/interview/exchanges/REQUIREMENTS.md)
- ✅ [app/audio/analysis/REQUIREMENTS.md](../app/audio/analysis/REQUIREMENTS.md)
- ✅ [app/interview/orchestration/REQUIREMENTS.md](../app/interview/orchestration/REQUIREMENTS.md)
- ✅ [app/interview/persistence/REQUIREMENTS.md](../app/interview/persistence/REQUIREMENTS.md)
- ✅ [app/audio/transcription/REQUIREMENTS.md](../app/audio/transcription/REQUIREMENTS.md)
- ✅ [app/ai/llm/REQUIREMENTS.md](../app/ai/llm/REQUIREMENTS.md)

Each file includes header:
```markdown
**See Also:** [Clarifications Architecture](../../docs/CLARIFICATIONS-ARCHITECTURE.md)
```

---

## 🧬 Key Design Patterns Introduced

### 1. Intent Classification Sandbox Pattern

```
Incoming Speech
    ↓ (DETERMINISTIC, temperature=0)
    ↓ (NO business logic)
Intent Classification
    ↓ (IMMUTABLE log)
Router (switch on intent)
    ├→ CLARIFICATION → Clarification Handler
    ├→ ANSWER → Response Processor
    ├→ INVALID → Repeat Request
    └→ POST_ANSWER → Rejection
```

### 2. Hydration Pattern for Clarifications

```
Exchange with:
    - clarification_count: 2
    - intent_sequence: [CLARIFICATION, CLARIFICATION, ANSWER]
    - final_intent: ANSWER
    
Can infer:
    - Candidate needed 2 clarifications
    - Progression of thinking
    - Final intent was answer (despite clarifications)
```

### 3. Policy Validation Before Exposure

```
LLM Response (temperature=0)
    ↓
Policy Validator (regex + word list)
    ├→ ✅ Pass: Return response
    └→ ❌ Fail: Log violation, return safe fallback
```

---

## 📊 Data Model Changes

### interview_exchanges Table (Extended)

```sql
ALTER TABLE interview_exchanges ADD COLUMN (
    clarification_count INTEGER NOT NULL DEFAULT 0 CHECK (clarification_count >= 0),
    clarification_limit_exceeded BOOLEAN NOT NULL DEFAULT FALSE,
    clarification_exchange_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    intent_sequence JSONB NOT NULL DEFAULT '[]'::JSONB,
    final_intent VARCHAR(50),
    final_intent_confidence FLOAT CHECK (final_intent_confidence >= 0.0 AND final_intent_confidence <= 1.0)
);

CREATE INDEX idx_exchanges_clarification_count ON interview_exchanges(clarification_count);
```

### interview_submissions Table (Extended)

```sql
ALTER TABLE interview_submissions ADD COLUMN (
    total_clarifications_requested INTEGER NOT NULL DEFAULT 0,
    total_clarifications_granted INTEGER NOT NULL DEFAULT 0,
    total_auto_skips_due_to_clarification INTEGER NOT NULL DEFAULT 0,
    clarification_audit_log JSONB NOT NULL DEFAULT '[]'::JSONB
);
```

---

## 🎓 Behavioral Changes

### Before

1. Candidate asks clarification
2. System: [unpredictable LLM response with potential hints]
3. ...repeat (no limit)
4. Exchange created eventually
5. No audit trail

### After

1. Candidate speaks → **Intent Classification (temperature=0, immutable)**
2. If CLARIFICATION:
   - Check: clarif_count < 3?
   - If ≥3: Auto-skip with neutral message
   - If <3: LLM with strict policy (temperature=0)
   - Response validated against prohibition list
   - Clarification count incremented
   - Audit log updated
3. Replay question
4. Repeat until ANSWER
5. Exchange created only with intent=ANSWER
6. Complete audit trail enables fairness review

---

## 🛡️ Risk Mitigations

| Risk | Mitigation in This Update |
|------|---------------------------|
| **LLM Hint Drift** | Policy validator with regex patterns + word list; temperature=0 |
| **Fairness Violation** | Clarification counts tracked per submission; audit log enables comparison |
| **Infinite Recursion** | Max 3 clarifications hard limit; auto-skip auto-triggers NEXT_QUESTION |
| **ASR Misclassification** | Confidence threshold (0.70); ask repeat if uncertain |
| **Modification After Submission** | POST_ANSWER intent detected; rejected with neutral message |
| **Audit Trail Corruption** | Immutable logging at every step; append-only audit tables |

---

## ✅ Acceptance Criteria Achieved

- ✅ Max clarifications = 3 (hard limit)
- ✅ Auto-skip on limit exceeded
- ✅ Intent classification runs FIRST (deterministic)
- ✅ LLM clarifications have strict policy (no hints drift)
- ✅ Immutable audit logging at every step
- ✅ Fairness tracking per submission
- ✅ ASR risk mitigation (confidence threshold)
- ✅ State machine formalized with clarifications
- ✅ All modules cross-referenced with master architecture doc

---

## 🚀 Next Steps (Implementation)

1. **Database Migrations**
   - Create migration file for new columns
   - Add indexes for clarification tracking

2. **Code Implementation**
   - Implement `IntentClassifier` in `app/audio/analysis/`
   - Implement `ClarificationValidator` in `app/ai/llm/`
   - Implement `ClarificationCoordinator` in `app/interview/orchestration/`
   - Update `ExchangeRepository` to handle new fields

3. **Configuration**
   - Set clarification policy flags (max_clarifications=3, allow_hint=False)
   - Configure intent classifier model
   - Set ASR confidence threshold

4. **Testing**
   - Unit tests: Intent classification edge cases
   - Integration tests: Full clarification flow
   - Fairness tests: Audit log integrity
   - Regression tests: Existing interview flows unaffected

5. **Documentation**
   - Developer guide for intent classification
   - Candidate FAQ on clarification limits
   - Admin guide for reviewing audit logs

---

## 📞 Questions?

Refer to:
1. [docs/CLARIFICATIONS-ARCHITECTURE.md](../docs/CLARIFICATIONS-ARCHITECTURE.md) - High-level overview
2. Module REQUIREMENTS files (linked above) - Implementation details
3. Schema definitions in this document - Database structure

---

**Status:** ✅ COMPLETE  
**Date:** February 17, 2026  
**Version:** 1.0  
**Reviewed By:** Architecture Team
