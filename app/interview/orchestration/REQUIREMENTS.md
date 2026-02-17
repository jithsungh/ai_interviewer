# Interview Orchestration - Runtime Coordination Layer

**See Also:** [Clarifications Architecture](../../docs/CLARIFICATIONS-ARCHITECTURE.md) - High-level overview of intent classification, clarification coordination, and state machine flow.

## 1. Purpose

The **Orchestration** layer is the **runtime brain** of the interview module. It:

- Resolves next question deterministically from template snapshot
- Coordinates exchange lifecycle (question → response → evaluation)
- Handles audio completion signals (silence detection)
- Handles code execution completion
- Manages race conditions between audio/code/evaluation
- Updates progress tracking (current_exchange_sequence)
- Maintains Redis session state

**Critical responsibility:** This is the **central coordinator**. It must:

- Use template snapshot (NEVER dynamically resolve template)
- Enforce deterministic question sequencing
- Prevent duplicate exchange creation
- Wait for complete response before creating exchange
- Trigger evaluation ONLY after exchange persisted
- Handle concurrency safely (audio + code race)

**Architectural philosophy:**

> **The orchestration layer COORDINATES. It does NOT score, parse rubrics, or make AI calls.**
> **It delegates to domain modules: question, coding, audio, evaluation.**
> **It enforces architectural invariants at runtime.**

---

## 2. Module Structure

```
orchestration/
├── question_sequencer.py   # Resolve next question from template snapshot
├── exchange_coordinator.py # Manage exchange lifecycle
├── audio_handler.py         # Handle audio completion signals
├── coding_handler.py        # Handle code execution completion
├── progress_tracker.py      # Update current_exchange_sequence
└── race_resolver.py         # Resolve audio/code race conditions
```

---

## 3. Question Sequencing

### Purpose

Resolve next question deterministically from **frozen template snapshot**.

### Critical Rule

**MUST USE:**

- `interview_submissions.template_structure_snapshot` (JSONB, frozen at creation)

**MUST NOT USE:**

- Dynamic JOIN to `interview_templates` table
- Runtime role → template resolution
- Live template configuration

**Why:** Template changes after interview starts must NOT affect in-progress interviews.

---

### Template Snapshot Structure

```json
{
  "template_id": 3,
  "template_name": "Full Stack Engineer Interview",
  "sections": [
    {
      "section_name": "resume",
      "question_count": 2,
      "question_ids": [101, 102]
    },
    {
      "section_name": "behavioral",
      "question_count": 3,
      "question_ids": [201, 202, 203]
    },
    {
      "section_name": "coding",
      "question_count": 3,
      "question_ids": [301, 302, 303]
    }
  ],
  "total_questions": 8
}
```

---

### Next Question Resolution

```python
from typing import Optional
from pydantic import BaseModel

class NextQuestionResult(BaseModel):
    question_id: int
    sequence_order: int
    section_name: str
    is_final_question: bool

def resolve_next_question(
    template_snapshot: dict,
    current_sequence: int
) -> Optional[NextQuestionResult]:
    """
    Resolve next question from template snapshot.

    Args:
        template_snapshot: Frozen template structure (from submission)
        current_sequence: Current exchange sequence (0-indexed)

    Returns:
        NextQuestionResult if more questions available, None if complete
    """
    sections = template_snapshot['sections']
    total_questions = template_snapshot['total_questions']

    # Check if complete
    if current_sequence >= total_questions:
        return None

    # Find question by flattening sequence
    question_index = 0
    for section in sections:
        section_count = section['question_count']

        if question_index + section_count > current_sequence:
            # Question is in this section
            local_index = current_sequence - question_index
            question_id = section['question_ids'][local_index]

            return NextQuestionResult(
                question_id=question_id,
                sequence_order=current_sequence + 1,  # 1-indexed
                section_name=section['section_name'],
                is_final_question=(current_sequence == total_questions - 1)
            )

        question_index += section_count

    # Should never reach here if total_questions correct
    raise ValueError("Question sequencing error")
```

**Example:**

- Template has 8 total questions: [101, 102, 201, 202, 203, 301, 302, 303]
- current_sequence = 0 → question_id = 101, sequence_order = 1
- current_sequence = 2 → question_id = 201, sequence_order = 3
- current_sequence = 7 → question_id = 303, sequence_order = 8, is_final = true

---

### Question Fetching

```python
from typing import Optional

class QuestionDTO(BaseModel):
    question_id: int
    question_text: str
    question_type: str  # 'text', 'coding', 'audio'
    question_difficulty: str
    expected_answer: Optional[str]
    time_limit_seconds: Optional[int]

async def fetch_question_content(question_id: int) -> QuestionDTO:
    """
    Fetch question content from question module.

    Delegates to question module.
    """
    # Call question module repository
    question = await question_service.get_by_id(question_id)

    if not question:
        raise QuestionNotFoundError(f"Question {question_id} not found")

    return QuestionDTO(
        question_id=question.id,
        question_text=question.content,
        question_type=question.question_type,
        question_difficulty=question.difficulty,
        expected_answer=question.expected_answer,
        time_limit_seconds=question.time_limit_seconds
    )
```

---

## 3a. Clarification Coordination (Strict Bounds)

### Purpose

Orchestrate clarification requests with hard limits and immutable logging.

### Clarification State Machine

```
WAITING_INPUT (clarification_count = 0)
    ↓
Candidate says: "What do you mean by X?"
    ↓ [Intent Classification = CLARIFICATION]
    ↓
LLM provides clarification (<120 words)
    ↓
Update: clarification_count = 1
    ↓
Replay question to candidate
    ↓
Go back to WAITING_INPUT
    ↓
[If clarification_count >= 3]:
    ├─ Lock clarifications
    ├─ Auto transition to ANSWER_SUBMITTED
    ├─ Log reason: CLARIFICATION_LIMIT_EXCEEDED
    └─ System response: "Answer has been recorded."
```

### Clarification Request Handler

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ClarificationRequest:
    submission_id: int
    exchange_sequence: int
    question_id: int
    question_text: str
    candidate_request: str         # What they asked
    current_clarification_count: int

async def handle_clarification_request(
    db: Session,
    redis: Redis,
    request: ClarificationRequest
) -> dict:
    """
    Process clarification request with strict bounds.
    
    Steps:
    1. Check if clarification_count < 3
    2. If >= 3: auto-skip, log reason, return skip message
    3. If < 3: call LLM with strict constraints
    4. Log clarification attempt immutably
    5. Increment clarification_count
    6. Return clarification response + replay instruction
    
    Returns:
        {
            "action": "provide_clarification" | "auto_skip",
            "clarification_text": str | None,
            "new_clarification_count": int,
            "message": str,
            "replay_question": bool
        }
    """
    
    # Step 1: Check limit
    if request.current_clarification_count >= 3:
        # Auto-skip
        log_clarification_event(
            submission_id=request.submission_id,
            exchange_sequence=request.exchange_sequence,
            event_type="CLARIFICATION_LIMIT_EXCEEDED",
            reason="max_clarifications_reached"
        )
        
        return {
            "action": "auto_skip",
            "clarification_text": None,
            "new_clarification_count": request.current_clarification_count,
            "message": "Answer has been recorded. Moving to next question.",
            "replay_question": False
        }
    
    # Step 2: Call LLM for clarification (with strict constraints)
    clarification_response = await call_clarification_llm(
        original_question=request.question_text,
        candidate_request=request.candidate_request,
        constraints={
            "MAX_WORDS": 120,
            "ALLOW_ANALOGY": True,
            "ANALOGY_COUNT": 1,
            "ALLOW_HINT": False,
            "PROHIBITIONS": [
                "algorithm_suggestions",
                "data_structure_suggestions",
                "step_sequencing",
                "partial_validation",
                "encouraging_phrases",
                "answer_description",
                "solution_examples"
            ]
        }
    )
    
    # Step 3: Validate LLM response
    if clarification_response['violates_policy']:
        # Log violation for audit
        log_policy_violation(
            submission_id=request.submission_id,
            clarification_text=clarification_response['text'],
            violation_reason=clarification_response['violation_reason']
        )
        
        # Fall back to neutral response
        safe_response = "I can't provide that clarification. Please rephrase your question."
    else:
        safe_response = clarification_response['text']
    
    # Step 4: Increment counter in submission
    submission = db.query(InterviewSubmission).filter(
        InterviewSubmission.id == request.submission_id
    ).first()
    
    new_count = request.current_clarification_count + 1
    submission.total_clarifications_granted += 1
    
    # Log to audit trail
    audit_entry = {
        "exchange_sequence": request.exchange_sequence,
        "question_id": request.question_id,
        "clarification_number": new_count,
        "candidate_request": request.candidate_request,
        "llm_response": safe_response,
        "timestamp": datetime.utcnow().isoformat(),
        "violates_policy": clarification_response.get('violates_policy', False)
    }
    
    submission.clarification_audit_log = submission.clarification_audit_log or []
    submission.clarification_audit_log.append(audit_entry)
    db.commit()
    
    # Step 5: Return response
    return {
        "action": "provide_clarification",
        "clarification_text": safe_response,
        "new_clarification_count": new_count,
        "message": safe_response,
        "replay_question": True
    }
```

### Clarification LLM Call (Strict Temperature=0)

```python
async def call_clarification_llm(
    original_question: str,
    candidate_request: str,
    constraints: dict
) -> dict:
    """
    Call LLM for clarification with STRICT constraints.
    
    Returns:
        {
            "text": str,
            "contains_hint": bool,
            "contains_analogy": bool,
            "violates_policy": bool,
            "violation_reason": Optional[str]
        }
    
    Critical:
    - Temperature must be 0 (deterministic)
    - Response must be <120 words
    - No algorithm suggestions
    - No "you're on the right track" 
    - No examples with solution code
    """
    
    system_prompt = f"""
You are a clarification assistant for coding interviews.

ORIGINAL QUESTION:
{original_question}

CANDIDATE CLARIFICATION REQUEST:
{candidate_request}

CONSTRAINTS:
- Maximum response length: {constraints['MAX_WORDS']} words
- You MAY define ambiguous terms
- You MAY rephrase the question
- You MAY provide at most 1 abstract analogy per question
- You MUST NOT suggest algorithms (e.g., "use DFS")
- You MUST NOT suggest data structures (e.g., "use a hash table")
- You MUST NOT give hints about the approach
- You MUST NOT validate the candidate's attempt
- You MUST NOT use encouraging phrases ("you're on the right track")
- You MUST NOT describe the answer
- Response must be NATURAL LANGUAGE ONLY (no JSON, no scoring)

Provide a brief, helpful clarification if possible. Otherwise, ask candidate to rephrase.
"""
    
    response = await llm_provider.call(
        model="gpt-4",  # or similar
        messages=[{"role": "system", "content": system_prompt}],
        temperature=0.0,  # ⭐ DETERMINISTIC
        max_tokens=150,
        timeout=5  # Fast timeout
    )
    
    clarification_text = response.choices[0].message.content.strip()
    
    # Post-processing: validate against policy
    violations = validate_clarification_policy(clarification_text, constraints)
    
    return {
        "text": clarification_text,
        "contains_hint": "hint" in clarification_text.lower(),
        "contains_analogy": "like" in clarification_text.lower() or "similar to" in clarification_text.lower(),
        "violates_policy": len(violations) > 0,
        "violation_reason": violations[0] if violations else None,
        "word_count": len(clarification_text.split())
    }

def validate_clarification_policy(text: str, constraints: dict) -> List[str]:
    """Check if clarification violates policy."""
    violations = []
    text_lower = text.lower()
    
    # Check word count
    word_count = len(text.split())
    if word_count > constraints['MAX_WORDS']:
        violations.append(f"Exceeds max words ({word_count} > {constraints['MAX_WORDS']})")
    
    # Check prohibitions
    prohibited_phrases = {
        "algorithm": ["use dfs", "use bfs", "use dijkstra", "use dynamic programming"],
        "data_structure": ["hash table", "linked list", "binary tree", "heap"],
        "step_sequencing": ["first", "then", "next step"],
        "partial_validation": ["you're right", "correct", "good approach"],
        "encouraging": ["you're on the right", "great", "excellent"],
        "answer_description": ["the answer is", "solution is", "implement"]
    }
    
    for category, phrases in prohibited_phrases.items():
        if any(phrase in text_lower for phrase in phrases):
            violations.append(f"Violates: {category}")
    
    return violations
```

---

## 3b. Intent Classification → State Machine

### Integration: Audio Input → Intent → State

```python
async def handle_candidate_utterance(
    submission_id: int,
    transcript: str,
    asr_confidence: float,
    question_context: str
) -> dict:
    """
    Main entry point for candidate speech.
    
    Flow:
    1. Classify intent (temperature=0)
    2. Route based on intent
    3. Update state machine + audit logs
    4. Return action to client
    """
    
    # Step 1: Intent classification (FIRST)
    intent = await intent_classifier.classify(IntentClassificationRequest(
        transcript=transcript,
        confidence_score=asr_confidence,
        question_context=question_context
    ))
    
    # Step 2: Log intent (immutably)
    log_intent_classification(intent)
    
    # Step 3: Route based on intent
    if intent.intent == "INVALID":
        return request_repeat(asr_confidence)
    
    elif intent.intent == "REPEAT":
        return replay_question(submission_id)
    
    elif intent.intent == "CLARIFICATION":
        # Get current clarification count from submission
        submission = db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        ).first()
        
        return await handle_clarification_request(
            db, redis,
            ClarificationRequest(
                submission_id=submission_id,
                exchange_sequence=submission.current_exchange_sequence,
                question_id=...,  # from context
                question_text=question_context,
                candidate_request=transcript,
                current_clarification_count=submission.total_clarifications_granted
            )
        )
    
    elif intent.intent == "INCOMPLETE":
        return wait_for_more_input(submission_id)
    
    elif intent.intent == "ANSWER":
        # Process answer
        return process_answer_submission(submission_id, transcript)
    
    elif intent.intent == "POST_ANSWER":
        # Reject modification
        return {
            "action": "reject",
            "message": "Answer has been recorded. Moving to next question."
        }
    
    else:  # UNKNOWN
        return ask_for_clarification(submission_id)
```

---

## 4. Exchange Lifecycle Coordination

### Purpose

Coordinate the complete lifecycle of an exchange:

1. Resolve next question
2. Deliver question to client (via WebSocket)
3. Receive response (text, code, audio)
4. Wait for response completion (code execution, audio processing)
5. Create immutable exchange
6. Trigger evaluation
7. Update progress
8. Deliver next question (if not final)

---

### Exchange Creation Flow

```python
from datetime import datetime

class ExchangeCreationRequest(BaseModel):
    submission_id: int
    sequence_order: int
    question_id: int
    question_text: str
    question_type: str
    question_difficulty: str
    section_name: str
    response_text: Optional[str] = None
    response_code: Optional[str] = None
    response_language: Optional[str] = None
    response_time_ms: int
    code_submission_id: Optional[int] = None
    audio_recording_id: Optional[int] = None

async def create_exchange(
    db: Session,
    redis: Redis,
    request: ExchangeCreationRequest
) -> InterviewExchange:
    """
    Create immutable exchange.

    Steps:
    1. Validate submission exists and in_progress
    2. Check no duplicate exchange for sequence
    3. Create exchange record
    4. Update current_exchange_sequence
    5. Update Redis session state
    6. Trigger evaluation (async)
    7. Emit ExchangeCreated event

    Raises:
        DuplicateExchangeError: Exchange already exists for sequence
        InvalidStateError: Submission not in_progress
    """
    # Step 1: Acquire lock
    lock_key = f"exchange_lock:{request.submission_id}:{request.sequence_order}"
    lock_value = str(uuid.uuid4())
    acquired = redis.set(lock_key, lock_value, nx=True, ex=10)

    if not acquired:
        # Concurrent request, check if exchange already created
        existing = db.query(InterviewExchange).filter(
            InterviewExchange.interview_submission_id == request.submission_id,
            InterviewExchange.sequence_order == request.sequence_order
        ).first()

        if existing:
            return existing  # Idempotent

        raise ConcurrencyError("Exchange creation in progress")

    try:
        # Step 2: Validate submission
        submission = db.query(InterviewSubmission).filter(
            InterviewSubmission.id == request.submission_id
        ).first()

        if not submission:
            raise NotFoundError(f"Submission {request.submission_id} not found")

        if submission.submission_status != 'in_progress':
            raise InvalidStateError(
                f"Cannot create exchange for submission in '{submission.submission_status}' state"
            )

        # Step 3: Check duplicate
        existing = db.query(InterviewExchange).filter(
            InterviewExchange.interview_submission_id == request.submission_id,
            InterviewExchange.sequence_order == request.sequence_order
        ).first()

        if existing:
            return existing  # Idempotent

        # Step 4: Create exchange
        exchange = InterviewExchange(
            interview_submission_id=request.submission_id,
            sequence_order=request.sequence_order,
            question_id=request.question_id,
            question_text=request.question_text,  # SNAPSHOT
            question_type=request.question_type,
            question_difficulty=request.question_difficulty,
            section_name=request.section_name,
            response_text=request.response_text,
            response_code=request.response_code,
            response_language=request.response_language,
            response_time_ms=request.response_time_ms,
            code_submission_id=request.code_submission_id,
            audio_recording_id=request.audio_recording_id,
            responded_at=datetime.utcnow()
        )

        db.add(exchange)
        db.commit()
        db.refresh(exchange)

        # Step 5: Update progress
        submission.current_exchange_sequence = request.sequence_order
        db.commit()

        # Step 6: Update Redis
        update_session_progress(redis, request.submission_id, request.sequence_order)

        # Step 7: Trigger evaluation (async, non-blocking)
        trigger_evaluation_async(exchange.id)

        # Step 8: Emit event
        emit_event({
            "event_type": "exchange_created",
            "exchange_id": exchange.id,
            "submission_id": request.submission_id,
            "sequence_order": request.sequence_order
        })

        return exchange

    finally:
        # Release lock
        current_value = redis.get(lock_key)
        if current_value and current_value.decode() == lock_value:
            redis.delete(lock_key)
```

---

## 5. Audio Completion Handling

### Purpose

Handle audio completion signals from audio module (silence detected).

### Audio Module Integration

**Audio module emits event:**

```json
{
  "event_type": "audio_silence_detected",
  "recording_id": 456,
  "submission_id": 123,
  "sequence_order": 5,
  "silence_duration_ms": 3000,
  "transcription_complete": true
}
```

**Orchestration layer handles:**

1. Verify submission is in_progress
2. Verify sequence_order matches current_exchange_sequence + 1
3. Fetch audio recording with transcription
4. Create exchange with response_text = transcription
5. Trigger evaluation

---

### Audio Handler

```python
async def handle_audio_completion(
    db: Session,
    redis: Redis,
    recording_id: int,
    submission_id: int,
    sequence_order: int
) -> InterviewExchange:
    """
    Handle audio completion signal.

    Steps:
    1. Fetch audio recording with transcription
    2. Resolve question for sequence
    3. Create exchange with transcription as response_text

    Raises:
        InvalidStateError: Submission not in_progress
        SequenceMismatchError: sequence_order doesn't match expected
    """
    # Step 1: Validate submission state
    submission = db.query(InterviewSubmission).filter(
        InterviewSubmission.id == submission_id
    ).first()

    if submission.submission_status != 'in_progress':
        raise InvalidStateError("Submission not in progress")

    # Step 2: Validate sequence
    expected_sequence = submission.current_exchange_sequence + 1
    if sequence_order != expected_sequence:
        # Race condition: exchange already created by another handler
        logger.warning(
            f"Audio completion for sequence {sequence_order}, but current is {expected_sequence}"
        )
        # Check if exchange already exists
        existing = db.query(InterviewExchange).filter(
            InterviewExchange.interview_submission_id == submission_id,
            InterviewExchange.sequence_order == sequence_order
        ).first()

        if existing:
            return existing  # Idempotent

        raise SequenceMismatchError("Sequence mismatch")

    # Step 3: Fetch audio recording
    audio_recording = await audio_service.get_recording(recording_id)

    if not audio_recording or not audio_recording.transcription:
        raise AudioNotReadyError("Transcription not complete")

    # Step 4: Resolve question
    template_snapshot = submission.template_structure_snapshot
    next_question = resolve_next_question(template_snapshot, submission.current_exchange_sequence)

    if not next_question or next_question.sequence_order != sequence_order:
        raise QuestionMismatchError("Question sequencing error")

    question = await fetch_question_content(next_question.question_id)

    # Step 5: Create exchange
    exchange = await create_exchange(db, redis, ExchangeCreationRequest(
        submission_id=submission_id,
        sequence_order=sequence_order,
        question_id=question.question_id,
        question_text=question.question_text,
        question_type='audio',
        question_difficulty=question.question_difficulty,
        section_name=next_question.section_name,
        response_text=audio_recording.transcription,
        response_time_ms=audio_recording.duration_ms,
        audio_recording_id=recording_id
    ))

    return exchange
```

---

## 6. Code Execution Completion Handling

### Purpose

Handle code execution completion signals from coding module.

### Coding Module Integration

**Coding module emits event:**

```json
{
  "event_type": "code_execution_completed",
  "code_submission_id": 789,
  "submission_id": 123,
  "sequence_order": 7,
  "execution_status": "passed",
  "score": 85.5
}
```

**Orchestration layer handles:**

1. Verify submission is in_progress
2. Verify sequence_order matches expected
3. Fetch code submission with execution results
4. Create exchange with response_code + execution results
5. Trigger evaluation

---

### Code Handler

```python
async def handle_code_completion(
    db: Session,
    redis: Redis,
    code_submission_id: int,
    submission_id: int,
    sequence_order: int
) -> InterviewExchange:
    """
    Handle code execution completion signal.

    Steps:
    1. Fetch code submission with execution results
    2. Resolve question for sequence
    3. Create exchange with code as response_code

    Raises:
        InvalidStateError: Submission not in_progress
        CodeNotReadyError: Execution not complete
    """
    # Similar structure to audio handler
    # ...

    # Fetch code submission
    code_submission = await coding_service.get_submission(code_submission_id)

    if not code_submission or code_submission.execution_status == 'pending':
        raise CodeNotReadyError("Code execution not complete")

    # Create exchange
    exchange = await create_exchange(db, redis, ExchangeCreationRequest(
        submission_id=submission_id,
        sequence_order=sequence_order,
        question_id=question.question_id,
        question_text=question.question_text,
        question_type='coding',
        question_difficulty=question.question_difficulty,
        section_name=next_question.section_name,
        response_code=code_submission.code,
        response_language=code_submission.language,
        response_time_ms=code_submission.response_time_ms,
        code_submission_id=code_submission_id
    ))

    return exchange
```

---

## 7. Race Condition Resolution

### Problem: Audio + Code Simultaneous Completion

**Scenario:**

- Audio detects silence at T=30.000s
- Code execution completes at T=30.001s
- Both trigger exchange creation for same sequence_order

**Solution:**

1. Redis lock: `exchange_lock:{submission_id}:{sequence_order}`
2. First handler acquires lock, creates exchange
3. Second handler cannot acquire lock, checks if exchange exists
4. Second handler finds existing exchange, returns it (idempotent)

**Implementation already in `create_exchange` function above.**

---

### Problem: Late Response After Timeout

**Scenario:**

- Interview expires at T=60:00
- Audio completion signal arrives at T=60:05

**Solution:**

1. Check submission status before creating exchange
2. If status = 'expired' or 'completed', reject with InvalidStateError
3. Do NOT create exchange for expired interview

**Implementation:**

```python
# In create_exchange function
if submission.submission_status != 'in_progress':
    raise InvalidStateError(
        f"Cannot create exchange for submission in '{submission.submission_status}' state"
    )
```

---

## 8. Progress Tracking

### Purpose

Update `current_exchange_sequence` after each exchange creation.

### Update Pattern

```python
def update_session_progress(
    redis: Redis,
    submission_id: int,
    sequence_order: int
) -> None:
    """
    Update Redis session progress.

    Updates:
    - current_exchange_sequence
    - progress_percentage
    """
    session_key = f"interview_session:{submission_id}"
    session_data = redis.get(session_key)

    if session_data:
        session = json.loads(session_data)
        total_questions = session.get('total_questions', 0)

        session['current_sequence'] = sequence_order
        session['progress_percentage'] = (sequence_order / total_questions) * 100 if total_questions > 0 else 0

        redis.set(session_key, json.dumps(session), ex=3900)
```

---

### Broadcast Progress (WebSocket)

```python
async def broadcast_progress_update(
    websocket_manager: WebSocketManager,
    submission_id: int,
    sequence_order: int,
    total_questions: int
) -> None:
    """
    Send progress update to client via WebSocket.
    """
    progress_percentage = (sequence_order / total_questions) * 100

    await websocket_manager.send_to_user(
        submission_id,
        {
            "event_type": "progress_update",
            "current_sequence": sequence_order,
            "total_questions": total_questions,
            "progress_percentage": round(progress_percentage, 2)
        }
    )
```

---

## 9. Evaluation Triggering

### Purpose

Trigger evaluation ONLY after exchange persisted.

### Critical Rule

**MUST:**

- Wait for exchange INSERT to commit
- Emit event with exchange_id
- Evaluation module handles asynchronously

**MUST NOT:**

- Trigger evaluation before exchange persisted (foreign key violation)
- Wait for evaluation completion (blocks exchange creation)

---

### Async Trigger Pattern

```python
def trigger_evaluation_async(exchange_id: int) -> None:
    """
    Trigger evaluation asynchronously (non-blocking).

    Emits event for evaluation worker to consume.
    """
    emit_event({
        "event_type": "exchange_created",
        "exchange_id": exchange_id,
        "timestamp": datetime.utcnow().isoformat()
    })

    # Evaluation module listens for ExchangeCreated event
    # Evaluation module calls POST /api/evaluation/evaluate
```

---

## 10. Timeout Handling

### Purpose

Auto-complete interview when time expires.

### Background Job

**Job:** Check for expired interviews every 60 seconds.

```python
async def timeout_monitor_job():
    """
    Background job to auto-complete expired interviews.

    Runs every 60 seconds.
    """
    while True:
        # Fetch expired submissions
        expired = db.query(InterviewSubmission).filter(
            InterviewSubmission.submission_status == 'in_progress',
            InterviewSubmission.expires_at < datetime.utcnow()
        ).limit(100).all()

        for submission in expired:
            try:
                # Transition state
                timeout_expired(db, submission.id)

                # Close WebSocket
                await websocket_manager.send_to_user(
                    submission.id,
                    {
                        "event_type": "interview_expired",
                        "message": "Interview time expired. Submitting automatically..."
                    }
                )

                await websocket_manager.close_connection(submission.id)

            except Exception as e:
                logger.error(f"Failed to expire submission {submission.id}: {e}")

        await asyncio.sleep(60)
```

---

## 11. Configuration

```python
# orchestration/config.py

class OrchestrationConfig(BaseModel):
    # Question Sequencing
    question_fetch_timeout_seconds: int = 5

    # Exchange Creation
    exchange_creation_lock_timeout_seconds: int = 10
    exchange_max_retries: int = 3

    # Race Condition Handling
    audio_completion_grace_period_seconds: int = 2
    code_completion_grace_period_seconds: int = 5

    # Progress Tracking
    progress_broadcast_enabled: bool = True

    # Evaluation Triggering
    evaluation_trigger_async: bool = True
    evaluation_trigger_timeout_seconds: int = 30
```

---

## 12. Testing Requirements

### Unit Tests

1. **Question sequencing:** Resolve correct question for sequence
2. **Template snapshot usage:** Never dynamic template resolution
3. **Race condition:** Duplicate exchange creation prevented
4. **State validation:** Exchange creation rejected for expired submission
5. **Sequence mismatch:** Audio/code completion for wrong sequence rejected

### Integration Tests

1. **Audio completion flow:** Audio signal → exchange created → evaluation triggered
2. **Code completion flow:** Code signal → exchange created → evaluation triggered
3. **Simultaneous audio + code:** Only one exchange created (idempotent)
4. **Late response after timeout:** Exchange creation rejected
5. **Progress tracking:** Redis session state updated after exchange

### Concurrency Tests

1. **Simultaneous exchange creation:** Lock prevents duplicate
2. **Lock timeout:** Lock released after 10s, retry succeeds
3. **Redis eviction:** Fallback to PostgreSQL

---

## 13. Critical Risks

1. **Dynamic template resolution:** Non-reproducible interviews (FORBIDDEN)
2. **Exchange created before response complete:** Incomplete data
3. **No race handling:** Duplicate exchanges created
4. **Evaluation triggered before exchange persisted:** Foreign key violation
5. **No timeout monitoring:** Expired interviews stuck in 'in_progress'
6. **No sequence validation:** Gaps in sequence_order
7. **Progress not tracked:** Client desync

---

**End of Interview Orchestration Requirements**
