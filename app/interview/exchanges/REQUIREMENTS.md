# Interview Exchanges - Immutable Exchange Creation & Snapshot Persistence

**See Also:** [Clarifications Architecture](../../docs/CLARIFICATIONS-ARCHITECTURE.md) - High-level overview of intent classification, clarifications, and fairness tracking.

## 1. Purpose

The **Exchanges** layer is responsible for:

- Creating immutable interview_exchanges (snapshot of question + response)
- Enforcing immutability at repository level (NO UPDATE queries)
- Snapshotting all question/response data at creation time
- Ensuring sequence_order integrity (no gaps, no duplicates)
- Preventing modification after creation

**Critical responsibility:** This is the **immutability enforcement boundary**. It must:

- Create exchange ONCE with complete snapshot data
- NEVER allow UPDATE on interview_exchanges table
- Raise error if update attempted
- Store copies of data, not references
- Validate completeness before creation

**Architectural philosophy:**

> **Exchanges are IMMUTABLE. Create once, never modify.**
> **Exchanges are SNAPSHOTS. Copy data, don't reference.**
> **Exchanges are SEQUENCED. No gaps, no duplicates.**

---

## 2. Intent Classification Taxonomy (Strict)

### Purpose

Every candidate utterance must be classified **deterministically** before any business logic runs. This ensures fair, auditable, and reproducible interviews.

### Classification Output Schema

```python
@dataclass
class UtteranceIntentClassification:
    intent: Literal[
        "ANSWER",              # Solution attempt (code logic, algorithm)
        "CLARIFICATION",       # Requesting clarification of question
        "REPEAT",              # Asking for question to be repeated
        "POST_ANSWER",         # Speech after submission (unsolicited)
        "INVALID",             # Unintelligible, silence, noise
        "INCOMPLETE",          # Fragment (incomplete thought, waiting to continue)
        "UNKNOWN",             # Ambiguous
    ]
    confidence: float          # 0.0-1.0 (classification confidence)
    contains_solution_attempt: bool  # True if solution logic detected
    semantic_level: Literal["none", "surface", "deep"]  # Depth of content
```

### Classification Rules

| Intent | Triggers | Examples |
|--------|----------|----------|
| **ANSWER** | Solution logic, algorithm steps, code-like language | "I would use a queue...", "My approach is...", "We can implement..." |
| **CLARIFICATION** | Question about wording, terms, constraints | "Can you rephrase that?", "What do you mean by...?" |
| **REPEAT** | Request to hear question again | "Can you say that again?", "Could you repeat?" |
| **POST_ANSWER** | Speech AFTER submission marked | Any utterance after response submitted |
| **INVALID** | Silence, unintelligible, noise, off-topic rambling | [Silence >3s], "hhh... umm..." (no content) |
| **INCOMPLETE** | Fragment suggesting more to come | "So... like...", "I think", "It would..." (incomplete sentence) |

### Classification Algorithm (Temperature = 0)

```python
class UtteranceIntentClassifier:
    """
    Lightweight intent classifier (can be separate model or LLM call with temperature=0).
    Must be fast (<500ms) and deterministic.
    """
    
    def classify(self, transcript: str, context: InterviewContext) -> UtteranceIntentClassification:
        """
        Classify utterance intent.
        
        Returns:
            UtteranceIntentClassification with strict deterministic output
        
        Raises:
            ClassificationError: If classification fails
        """
        raise NotImplementedError
```

### Critical Rules

1. **Default to ANSWER (conservative):** If ambiguity between CLARIFICATION + ANSWER → treat as ANSWER
2. **Temperature = 0 (or near 0):** No randomness in classification
3. **Immutable logging:** Every classification logged (audit trail)
4. **No evaluation logic before classification:** Classification runs FIRST

### Example Classifications

**Example 1: Mixed Clarification + Answer**
```
Transcript: "So this is about BFS right? I would use a queue..."

Classification:
  intent: ANSWER
  confidence: 0.95
  contains_solution_attempt: true
  semantic_level: deep
  
Reason: Contains "I would use" (solution logic). Treat as ANSWER.
```

**Example 2: Pure Clarification**
```
Transcript: "Can you define what you mean by 'optimal'?"

Classification:
  intent: CLARIFICATION
  confidence: 0.98
  contains_solution_attempt: false
  semantic_level: surface
```

**Example 3: Incomplete Fragment**
```
Transcript: "I think we could use... like..."

Classification:
  intent: INCOMPLETE
  confidence: 0.85
  contains_solution_attempt: false
  semantic_level: surface
  
Reason: Incomplete sentence, suggests candidate will continue.
```

---

## 3. Question State Machine with Clarifications

### State Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      ASKED                                       │
│          (Question presented to candidate)                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                  WAITING_INPUT                                   │
│     (Listening for candidate response)                           │
│     clarification_count: 0                                       │
└────┬────────────────┬────────────────┬──────────────────────────┘
     │                │                │
     │ (CLARIFICATION)│ (ANSWER)       │ (REPEAT)
     │                │                │
     ↓                ↓                ↓
┌──────────────────┐  │  ┌──────────────────────┐
│ CLARIFICATION    │  │  │ WAITING_INPUT        │
│ _REQUESTED       │  │  │ (same state)         │
│                  │  │  │ clarification_count++│
│ clarification    │  │  └──────────────────────┘
│ _count++         │  │
│                  │  │ (if count < 3, replay
│ (max 3)          │  │  question + wait again)
│                  │  │
└────────┬─────────┘  │
         │            │
         │ (response  │
         │  to clarif)│
         │            │
         └────┬───────┘
              │
         (if count >= 3,
         auto-skip;
         else loop back)
              │
              ↓
┌─────────────────────────────────────────────────────────────────┐
│              ANSWER_SUBMITTED                                    │
│        (Response received & recorded)                            │
│        clarification_count: final value                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│            POST_ANSWER_WINDOW (5-10 seconds)                     │
│     (Candidate may speak, but only recorded for info)            │
│     Any contribution rejected; "Answer recorded"                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│              EVALUATED                                           │
│       (Exchange immutably persisted)                             │
│       (Evaluation complete or pending)                           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│            NEXT_QUESTION                                         │
│   (Prepare next question or end interview)                       │
└─────────────────────────────────────────────────────────────────┘
```

### State Machine Entity: interview_exchanges (Extended)

```sql
CREATE TABLE interview_exchanges (
    id SERIAL PRIMARY KEY,
    interview_submission_id INTEGER NOT NULL REFERENCES interview_submissions(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,

    -- Question snapshot (IMMUTABLE)
    question_id INTEGER NOT NULL REFERENCES questions(id),
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL CHECK (
        question_type IN ('text', 'coding', 'audio')
    ),
    question_difficulty VARCHAR(20),
    expected_answer TEXT,
    section_name VARCHAR(50) NOT NULL,

    -- Response snapshot (IMMUTABLE)
    response_text TEXT,
    response_code TEXT,
    response_language VARCHAR(20),
    response_time_ms INTEGER,

    -- ⭐ CLARIFICATION TRACKING
    clarification_count INTEGER NOT NULL DEFAULT 0 CHECK (clarification_count >= 0),
    clarification_limit_exceeded BOOLEAN NOT NULL DEFAULT FALSE,
    clarification_exchange_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[],  -- IDs of clarification attempts
    
    -- ⭐ INTENT CLASSIFICATION AUDIT
    intent_sequence JSONB NOT NULL DEFAULT '[]'::JSONB,  -- Array of all intents in order
    final_intent VARCHAR(50),  -- Last classify intent (ANSWER, INVALID, etc)
    final_intent_confidence FLOAT CHECK (final_intent_confidence >= 0.0 AND final_intent_confidence <= 1.0),
    
    -- Foreign keys to related entities
    code_submission_id INTEGER REFERENCES code_submissions(id),
    audio_recording_id INTEGER REFERENCES audio_recordings(id),

    -- Metadata
    ai_followup_message TEXT,
    responded_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(interview_submission_id, sequence_order),
    UNIQUE(interview_submission_id, question_id),
    CHECK (
        (response_text IS NOT NULL AND question_type = 'text') OR
        (response_text IS NOT NULL AND question_type = 'audio') OR
        (response_code IS NOT NULL AND question_type = 'coding')
    )
);

CREATE INDEX idx_exchanges_submission ON interview_exchanges(interview_submission_id);
CREATE INDEX idx_exchanges_sequence ON interview_exchanges(interview_submission_id, sequence_order);
CREATE INDEX idx_exchanges_question ON interview_exchanges(question_id);
CREATE INDEX idx_exchanges_clarification_count ON interview_exchanges(clarification_count);
```

### State Machine Fields

```python
@dataclass
class ExchangeStateSnapshot:
    """Current state of an exchange through its lifecycle."""
    exchange_id: int
    current_state: Literal[
        "ASKED",
        "WAITING_INPUT",
        "CLARIFICATION_REQUESTED",
        "ANSWER_SUBMITTED",
        "POST_ANSWER_WINDOW",
        "EVALUATED",
        "NEXT_QUESTION"
    ]
    clarification_count: int          # Current count (0-3)
    clarification_limit_exceeded: bool  # True if count >= 3
    intent_sequence: List[UtteranceIntentClassification]  # All intents in order
    last_intent: Optional[UtteranceIntentClassification]  # Most recent classification
    response_locked: bool              # True after ANSWER_SUBMITTED
```

---

## 4. Clarification Policy (Strict Bounds)

### Max Clarifications = 3 Rule

```
IF clarification_count >= 3:
    → Lock clarification requests
    → Auto transition to ANSWER_SUBMITTED
    → Mark reason: CLARIFICATION_LIMIT_EXCEEDED
    → No emotional message (neutral system response)
    → Log event immutably
```

### What LLM Can Do During Clarification

**ALLOWED:**
- Rephrase question wording
- Define ambiguous terms
- Restate constraints (e.g., "You have 5 minutes")
- Provide abstract analogy (max 1 per question)
- Ask candidate to clarify THEIR interpretation

**RARELY ALLOWED (Quantified):**
- 1 conceptual example per question (max)
  - Must NOT show solution structure
  - Example: "Like sorting a deck of cards" (not "use quicksort")
- 1 micro-hint per question (optional, recommend: disable)
  - Micro-hint: "Think about X" (not "Use algorithm Y")
  - Both candidates must get identical hints for fairness

**FORBIDDEN:**
- Algorithm suggestions ("Use DFS")
- Data structure suggestions ("Use a hash table")
- Step sequencing ("First do X, then do Y")
- Partial solution validation ("That's the right direction")
- Encouraging phrases ("You're on the right track")
- Describing answer ("The answer involves recursion")
- Giving examples with solution code

### Clarification Prompt Contract

```python
CLARIFICATION_SYSTEM_PROMPT_CONSTRAINTS = {
    "MAX_WORDS": 120,
    "ALLOW_ANALOGY": True,
    "ANALOGY_COUNT": 1,  # Max 1 per question
    "ALLOW_HINT": False,  # Recommend: False for fairness
    "HINT_COUNT": 0,     # If enabled, max 1 per question
    "PROHIBITIONS": [
        "algorithm_suggestions",
        "data_structure_suggestions",
        "step_sequencing",
        "partial_validation",
        "encouraging_phrases",
        "answer_description",
        "solution_examples"
    ],
    "OUTPUT_FORMAT": "natural_language",  # No JSON, no scoring
}
```

### Clarification LLM Request Template

```python
@dataclass
class ClarificationRequest:
    original_question: str         # REQUIRED: Verbatim question text
    candidate_clarification_request: str  # What candidate asked
    clarification_count_so_far: int       # Current count (0-2)
    constraints: Dict[str, Any]   # Policy constraints (above)
    allow_hint: bool = False       # If True, max 1 hint allowed
    previous_clarifications: List[str] = []  # Prior clarifications given
    
    
class ClarificationResponse:
    clarification_text: str        # LLM response (<=120 words)
    contains_hint: bool            # True if hint given
    contains_analogy: bool         # True if analogy given
    violates_policy: bool          # True if policy violation detected
```

---

## 5. Clarification Audit Logging

### Log Schema (Immutable)

Every question's clarification activity must be logged:

```json
{
  "question_id": 101,
  "exchange_id": 5001,
  "submission_id": 1000,
  "clarification_count": 2,
  "clarification_limit_exceeded": false,
  "hint_given": false,
  "replays": 1,
  "auto_skipped": false,
  "final_intent_sequence": [
    {"intent": "CLARIFICATION", "confidence": 0.95, "timestamp_ms": 1000},
    {"intent": "CLARIFICATION", "confidence": 0.92, "timestamp_ms": 3500},
    {"intent": "ANSWER", "confidence": 0.88, "timestamp_ms": 8000}
  ],
  "fairness_score": {
    "clarification_equity": "fair",  # All candidates got similar # of clarifications
    "hint_given_equity": "fair"      # Either all got hints or none did
  }
}
```

### Critical for Audit

- Every classification logged immutably
- Every clarification decision logged
- Every auto-skip logged with reason
- Enables candidate defense ("I requested clarification X times")
- Enables fairness analysis (comparing similar candidates)

---

## 6. Voice-Specific ASR Risks

### Problem: ASR Misclassification

ASR noise or misrecognition can cause:

```
Actual speech: "I think maybe we can use recursion"
ASR error:     "I think may be we can lose recursion"
Classification: Could misclassify as INVALID or UNCLEAR
```

### Mitigation: Confidence Threshold

```python
class ASRConfidenceHandler:
    """Handle low-confidence ASR results."""
    
    ASR_CONFIDENCE_THRESHOLD = 0.70  # Below this, ask for repeat
    
    def should_ask_for_repeat(self, transcript: str, asr_confidence: float) -> bool:
        """
        If ASR confidence too low, ask candidate to repeat.
        
        Returns:
            True if repeat should be requested
        """
        if asr_confidence < self.ASR_CONFIDENCE_THRESHOLD:
            return True
        return False
    
    def build_repeat_request(self) -> str:
        """Build neutral repeat request."""
        return "I didn't quite catch that. Could you please repeat?"
```

---

## 2. Owned Entity

### interview_exchanges

```sql
CREATE TABLE interview_exchanges (
    id SERIAL PRIMARY KEY,
    interview_submission_id INTEGER NOT NULL REFERENCES interview_submissions(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,

    -- Question snapshot (IMMUTABLE)
    question_id INTEGER NOT NULL REFERENCES questions(id),
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL CHECK (
        question_type IN ('text', 'coding', 'audio')
    ),
    question_difficulty VARCHAR(20),
    expected_answer TEXT,
    section_name VARCHAR(50) NOT NULL,

    -- Response snapshot (IMMUTABLE)
    response_text TEXT,
    response_code TEXT,
    response_language VARCHAR(20),
    response_time_ms INTEGER,

    -- Foreign keys to related entities
    code_submission_id INTEGER REFERENCES code_submissions(id),
    audio_recording_id INTEGER REFERENCES audio_recordings(id),

    -- Metadata
    ai_followup_message TEXT,
    responded_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(interview_submission_id, sequence_order),
    UNIQUE(interview_submission_id, question_id),
    CHECK (
        (response_text IS NOT NULL AND question_type = 'text') OR
        (response_text IS NOT NULL AND question_type = 'audio') OR
        (response_code IS NOT NULL AND question_type = 'coding')
    )
);

CREATE INDEX idx_exchanges_submission ON interview_exchanges(interview_submission_id);
CREATE INDEX idx_exchanges_sequence ON interview_exchanges(interview_submission_id, sequence_order);
CREATE INDEX idx_exchanges_question ON interview_exchanges(question_id);
```

---

## 3. Immutability Contract

### Core Principle

**EXCHANGES ARE IMMUTABLE AFTER CREATION.**

Once an `interview_exchange` record is created, it MUST NEVER be modified.

### Implementation Rules

**ALLOWED:**

```python
# CREATE only
exchange = InterviewExchange(
    interview_submission_id=123,
    sequence_order=5,
    question_text="What is polymorphism?",  # SNAPSHOT
    response_text="Polymorphism is...",     # SNAPSHOT
    ...
)
db.add(exchange)
db.commit()
```

**FORBIDDEN:**

```python
# UPDATE (FORBIDDEN)
exchange.response_text = "Updated answer"
db.commit()

# DELETE individual exchange (CASCADE only)
db.delete(exchange)
db.commit()

# Raw UPDATE (FORBIDDEN)
db.execute("UPDATE interview_exchanges SET response_text = ... WHERE id = ...")
```

---

### Repository-Level Protection

```python
class InterviewExchangeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, exchange_data: dict) -> InterviewExchange:
        """Create exchange (ONLY operation allowed)."""
        exchange = InterviewExchange(**exchange_data)
        self.db.add(exchange)
        self.db.commit()
        self.db.refresh(exchange)
        return exchange

    def update(self, exchange_id: int, updates: dict) -> None:
        """
        UPDATE IS FORBIDDEN.

        Raises:
            ImmutabilityViolationError
        """
        raise ImmutabilityViolationError(
            "interview_exchanges are immutable. Cannot update after creation."
        )

    def delete(self, exchange_id: int) -> None:
        """
        DELETE IS FORBIDDEN (except CASCADE).

        Raises:
            ImmutabilityViolationError
        """
        raise ImmutabilityViolationError(
            "interview_exchanges cannot be deleted individually. "
            "Only deleted via CASCADE when submission deleted."
        )
```

---

## 4. Snapshot Creation

### Purpose

Capture complete question + response data at exchange creation time.

### What to Snapshot

**Question data (from questions table):**

- `question_id` (reference for joins, but also snapshot content)
- `question_text` (COPY, not reference)
- `question_type` (text, coding, audio)
- `question_difficulty` (easy, medium, hard)
- `expected_answer` (for evaluation context)
- `section_name` (resume, behavioral, coding, etc.)

**Response data (from candidate):**

- `response_text` (for text/audio questions)
- `response_code` (for coding questions)
- `response_language` (python, java, cpp)
- `response_time_ms` (milliseconds from question delivery to response)

**Related entities (references):**

- `code_submission_id` (if coding question)
- `audio_recording_id` (if audio question)

---

### Why Snapshot?

**Problem WITHOUT snapshot:**

1. Exchange stores only `question_id`
2. Admin updates question text in `questions` table
3. Historical exchange now shows updated question text
4. **Audit trail broken** - cannot reproduce original interview

**Solution WITH snapshot:**

1. Exchange stores `question_id` + `question_text` (copy)
2. Admin updates question text in `questions` table
3. Historical exchange shows ORIGINAL question text (snapshot)
4. **Audit trail preserved** - can reproduce exact interview

---

### Snapshot Example

```python
# Fetch question from question module
question = await question_service.get_by_id(101)

# Create exchange with SNAPSHOT
exchange = InterviewExchange(
    interview_submission_id=123,
    sequence_order=1,

    # Reference (for joins)
    question_id=101,

    # Snapshot (copy of data at creation time)
    question_text=question.content,           # COPY
    question_type=question.question_type,     # COPY
    question_difficulty=question.difficulty,  # COPY
    expected_answer=question.expected_answer, # COPY
    section_name="resume",

    # Response snapshot
    response_text="My answer is...",
    response_time_ms=45000,

    responded_at=datetime.utcnow()
)
```

---

## 5. Sequence Integrity

### Purpose

Ensure sequence_order is sequential, contiguous, and unique.

### Constraints

**Database constraints:**

1. `UNIQUE(interview_submission_id, sequence_order)` - No duplicate sequences
2. `UNIQUE(interview_submission_id, question_id)` - No duplicate questions

**Application-level validation:**

1. No gaps in sequence (1, 2, 3, ..., not 1, 2, 4, ...)
2. Sequence matches current_exchange_sequence + 1

---

### Sequence Validation

```python
def validate_sequence_order(
    db: Session,
    submission_id: int,
    proposed_sequence: int
) -> None:
    """
    Validate proposed sequence_order.

    Raises:
        SequenceGapError: Gap detected
        DuplicateSequenceError: Duplicate detected
    """
    # Fetch current exchange count
    current_count = db.query(InterviewExchange).filter(
        InterviewExchange.interview_submission_id == submission_id
    ).count()

    # Expected next sequence = current_count + 1
    expected_sequence = current_count + 1

    if proposed_sequence != expected_sequence:
        raise SequenceGapError(
            f"Expected sequence {expected_sequence}, got {proposed_sequence}"
        )

    # Check duplicate (redundant with UNIQUE constraint, but explicit)
    existing = db.query(InterviewExchange).filter(
        InterviewExchange.interview_submission_id == submission_id,
        InterviewExchange.sequence_order == proposed_sequence
    ).first()

    if existing:
        raise DuplicateSequenceError(
            f"Exchange already exists for sequence {proposed_sequence}"
        )
```

---

## 6. Response Completeness Validation

### Purpose

Ensure exchange created only after COMPLETE response received.

### Validation Rules

**For text questions:**

- `response_text` must be non-null
- `response_time_ms` must be > 0

**For audio questions:**

- `response_text` must be non-null (transcription)
- `audio_recording_id` must be non-null
- Audio recording must have completed transcription

**For coding questions:**

- `response_code` must be non-null
- `code_submission_id` must be non-null
- Code submission must have completed execution

---

### Validation Implementation

```python
def validate_response_completeness(exchange_data: dict) -> None:
    """
    Validate response completeness before exchange creation.

    Raises:
        IncompleteResponseError: Response data missing or incomplete
    """
    question_type = exchange_data.get('question_type')

    if question_type == 'text':
        if not exchange_data.get('response_text'):
            raise IncompleteResponseError("response_text required for text question")

    elif question_type == 'audio':
        if not exchange_data.get('response_text'):
            raise IncompleteResponseError("response_text (transcription) required for audio question")
        if not exchange_data.get('audio_recording_id'):
            raise IncompleteResponseError("audio_recording_id required for audio question")

    elif question_type == 'coding':
        if not exchange_data.get('response_code'):
            raise IncompleteResponseError("response_code required for coding question")
        if not exchange_data.get('code_submission_id'):
            raise IncompleteResponseError("code_submission_id required for coding question")

    else:
        raise ValueError(f"Unknown question_type: {question_type}")

    # Validate response_time_ms
    if exchange_data.get('response_time_ms', 0) <= 0:
        raise IncompleteResponseError("response_time_ms must be > 0")
```

---

## 7. Exchange Creation Process

### Complete Flow

```python
from typing import Optional

class ExchangeCreationData(BaseModel):
    submission_id: int
    sequence_order: int
    question_id: int
    question_text: str
    question_type: str
    question_difficulty: str
    section_name: str
    expected_answer: Optional[str] = None
    response_text: Optional[str] = None
    response_code: Optional[str] = None
    response_language: Optional[str] = None
    response_time_ms: int
    code_submission_id: Optional[int] = None
    audio_recording_id: Optional[int] = None
    ai_followup_message: Optional[str] = None

def create_exchange(
    db: Session,
    data: ExchangeCreationData
) -> InterviewExchange:
    """
    Create immutable exchange with complete validation.

    Steps:
    1. Validate submission exists and in_progress
    2. Validate sequence order (no gaps, no duplicates)
    3. Validate response completeness
    4. Create exchange (snapshot)
    5. Return created exchange

    Raises:
        InvalidStateError: Submission not in_progress
        SequenceGapError: Gap in sequence
        DuplicateSequenceError: Duplicate sequence
        IncompleteResponseError: Response data incomplete
        ImmutabilityViolationError: Attempted update
    """
    # Step 1: Validate submission state
    submission = db.query(InterviewSubmission).filter(
        InterviewSubmission.id == data.submission_id
    ).first()

    if not submission:
        raise NotFoundError(f"Submission {data.submission_id} not found")

    if submission.submission_status != 'in_progress':
        raise InvalidStateError(
            f"Cannot create exchange for submission in '{submission.submission_status}' state"
        )

    # Step 2: Validate sequence
    validate_sequence_order(db, data.submission_id, data.sequence_order)

    # Step 3: Validate response completeness
    validate_response_completeness(data.model_dump())

    # Step 4: Create exchange
    exchange = InterviewExchange(
        interview_submission_id=data.submission_id,
        sequence_order=data.sequence_order,
        question_id=data.question_id,
        question_text=data.question_text,
        question_type=data.question_type,
        question_difficulty=data.question_difficulty,
        expected_answer=data.expected_answer,
        section_name=data.section_name,
        response_text=data.response_text,
        response_code=data.response_code,
        response_language=data.response_language,
        response_time_ms=data.response_time_ms,
        code_submission_id=data.code_submission_id,
        audio_recording_id=data.audio_recording_id,
        ai_followup_message=data.ai_followup_message,
        responded_at=datetime.utcnow()
    )

    db.add(exchange)
    db.commit()
    db.refresh(exchange)

    return exchange
```

---

## 8. Retrieval Operations

### Fetch Exchange by ID

```python
def get_by_id(db: Session, exchange_id: int) -> Optional[InterviewExchange]:
    """Fetch exchange by ID."""
    return db.query(InterviewExchange).filter(
        InterviewExchange.id == exchange_id
    ).first()
```

---

### Fetch Exchanges by Submission

```python
def list_by_submission(
    db: Session,
    submission_id: int,
    order_by: str = "sequence_order"
) -> List[InterviewExchange]:
    """
    Fetch all exchanges for submission, ordered by sequence.
    """
    return db.query(InterviewExchange).filter(
        InterviewExchange.interview_submission_id == submission_id
    ).order_by(InterviewExchange.sequence_order).all()
```

---

### Fetch Exchanges by Section

```python
def list_by_section(
    db: Session,
    submission_id: int,
    section_name: str
) -> List[InterviewExchange]:
    """
    Fetch exchanges for specific section (e.g., 'coding').
    """
    return db.query(InterviewExchange).filter(
        InterviewExchange.interview_submission_id == submission_id,
        InterviewExchange.section_name == section_name
    ).order_by(InterviewExchange.sequence_order).all()
```

---

### Check Exchange Exists

```python
def exists_for_sequence(
    db: Session,
    submission_id: int,
    sequence_order: int
) -> bool:
    """
    Check if exchange exists for given sequence.

    Used for idempotency checks.
    """
    return db.query(
        db.query(InterviewExchange)
        .filter(
            InterviewExchange.interview_submission_id == submission_id,
            InterviewExchange.sequence_order == sequence_order
        )
        .exists()
    ).scalar()
```

---

## 9. Edge Cases

### 1. Duplicate Exchange Creation Attempt

**Scenario:** Network retry causes duplicate create request.

**Handling:**

- UNIQUE constraint on (submission_id, sequence_order) prevents duplicate
- IntegrityError raised
- Caller checks if exchange exists, returns existing (idempotent)

---

### 2. Question Updated After Exchange Created

**Scenario:** Admin updates question text after exchange created.

**Handling:**

- Exchange preserves original question_text (snapshot)
- New interviews use updated question text
- Historical exchanges show original (audit trail preserved)

---

### 3. Exchange Created Before Response Complete

**Scenario:** Code submitted, exchange created, but execution still pending.

**Handling:**

- FORBIDDEN: Validation rejects incomplete response
- Orchestration layer must wait for execution completion
- Only create exchange after code_submission.execution_status != 'pending'

---

### 4. Gap in Sequence Order

**Scenario:** Exchanges created with sequences 1, 2, 4 (missing 3).

**Handling:**

- Validation rejects: Expected sequence 3, got 4
- SequenceGapError raised
- Fix: Create sequence 3 exchange before sequence 4

---

### 5. Attempt to Update Exchange

**Scenario:** Admin tries to correct candidate's answer in exchange.

**Handling:**

- Repository.update() raises ImmutabilityViolationError
- Admin must use evaluation override instead
- Exchange remains immutable

---

## 10. Concurrency Considerations

### UNIQUE Constraint Protection

**Database constraint prevents duplicate exchanges:**

```sql
UNIQUE(interview_submission_id, sequence_order)
```

**If concurrent requests:**

1. First INSERT succeeds
2. Second INSERT fails with IntegrityError
3. Second request checks if exchange exists
4. Returns existing exchange (idempotent)

---

### Row-Level Locking (Optional)

**For extra safety, use lock in orchestration layer:**

```python
# In orchestration/exchange_coordinator.py
lock_key = f"exchange_lock:{submission_id}:{sequence_order}"
acquired = redis.set(lock_key, lock_value, nx=True, ex=10)
```

---

## 11. Testing Requirements

### Unit Tests

1. **Create exchange:** Valid data → exchange created
2. **Update attempt:** Raises ImmutabilityViolationError
3. **Delete attempt:** Raises ImmutabilityViolationError
4. **Sequence validation:** Gap detected → SequenceGapError
5. **Duplicate sequence:** Duplicate detected → IntegrityError
6. **Incomplete response:** Missing response_text → IncompleteResponseError

### Integration Tests

1. **Snapshot preservation:** Question updated, exchange shows original
2. **Sequence integrity:** Exchanges created in order 1, 2, 3, ...
3. **Concurrent creation:** Two requests, only one succeeds
4. **Idempotency:** Duplicate request returns existing exchange

### Edge Case Tests

1. **Gap in sequence:** Create 1, 2, 4 → rejected
2. **Create after completion:** Submission completed → InvalidStateError
3. **Create before response ready:** Code execution pending → IncompleteResponseError
4. **Update immutable exchange:** update() raises error

---

## 12. Critical Risks

1. **No immutability enforcement:** Exchanges mutated, audit trail corrupted
2. **No snapshot:** Question changes affect historical exchanges
3. **No sequence validation:** Gaps in sequence, inconsistent ordering
4. **No completeness check:** Exchange created with partial response
5. **Allow UPDATE queries:** Immutability violated
6. **Reference instead of copy:** Question data not snapshotted

---

## 13. Future Enhancements

1. **Soft delete:** Mark exchanges as deleted (visible = false)
2. **Versioning:** Support multiple versions of same exchange (re-answer)
3. **Encryption:** Encrypt sensitive response data at rest
4. **Archiving:** Move old exchanges to archive storage (S3)
5. **Compression:** Compress large response_code/response_text

---

**End of Interview Exchanges Requirements**
