# 🚀 Quick Start: Intent Classification & Clarification System

**For:** Developers implementing the new clarification architecture  
**Time to read:** 5-10 minutes  
**Pre-requisite:** Read [CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md)

---

## 📌 The 30-Second Pitch

```
Candidate's speech → Intent Classification (temp=0) → Auto-route
    ├─ ANSWER? → Create exchange
    ├─ CLARIFICATION? (count < 3) → Generate LLM response (temp=0, policy checked) → Replay question
    ├─ CLARIFICATION? (count >= 3) → Auto-skip (neutral message)
    ├─ INVALID? → Ask repeat
    ├─ POST_ANSWER? → Reject
    └─ Everything logged immutably
```

---

## 🔨 Implementation Checklist

### Phase 1: Data Model (1-2 days)

- [ ] Create migration: Add clarification columns to interview_exchanges
  - `clarification_count` INTEGER
  - `clarification_limit_exceeded` BOOLEAN
  - `intent_sequence` JSONB
  - `final_intent` VARCHAR(50)
  - `final_intent_confidence` FLOAT

- [ ] Create migration: Add tracking to interview_submissions
  - `total_clarifications_requested` INTEGER
  - `total_clarifications_granted` INTEGER
  - `total_auto_skips_due_to_clarification` INTEGER
  - `clarification_audit_log` JSONB

- [ ] Add indexes:
  ```sql
  CREATE INDEX idx_exchanges_clarification_count ON interview_exchanges(clarification_count);
  ```

### Phase 2: Intent Classification (2-3 days)

- [ ] Implement `IntentClassifier` in [app/audio/analysis/](app/audio/analysis/)
  - [ ] Input validation (transcript, confidence, context)
  - [ ] Rule-based NLP classification (solution keywords, clarification keywords, etc.)
  - [ ] Handle edge cases (empty, silence, low confidence)
  - [ ] Return `IntentClassificationResult` dataclass

- [ ] Add to [app/audio/ingestion/](app/audio/ingestion/) flow:
  ```python
  transcript = await transcription_service.transcribe(audio_bytes)
  intent = await intent_classifier.classify(IntentClassificationRequest(
      transcript=transcript.text,
      confidence_score=transcript.confidence,
      question_context=current_question.text
  ))
  log_intent_classification(intent)  # ← IMMUTABLE FIRST
  await orchestration_service.handle_candidate_input(intent)
  ```

- [ ] Unit tests:
  - [ ] ANSWER intent (solution keywords)
  - [ ] CLARIFICATION intent (question keywords)
  - [ ] INVALID intent (empty/silence)
  - [ ] INCOMPLETE intent (fragment)
  - [ ] UNKNOWN intent (ambiguous)

### Phase 3: Clarification Handler (2-3 days)

- [ ] Implement `ClarificationCoordinator` in [app/interview/orchestration/](app/interview/orchestration/)
  - [ ] Check clarification count < 3
  - [ ] If >= 3: Auto-skip (log reason)
  - [ ] If < 3: Call LLM generator
  - [ ] Validate response against policy
  - [ ] Increment counter
  - [ ] Log immutably
  - [ ] Return clarification + replay instruction

- [ ] Implement `generate_clarification()` in [app/ai/llm/](app/ai/llm/)
  - [ ] System prompt with constraints
  - [ ] temperature=0 (CRITICAL)
  - [ ] max_tokens=150
  - [ ] timeout=5 seconds
  - [ ] Call LLM provider

- [ ] Implement `ClarificationValidator` in [app/ai/llm/](app/ai/llm/)
  - [ ] Word count check (≤ 120)
  - [ ] Prohibited patterns (regex)
  - [ ] Prohibited word list
  - [ ] Hint/analogy count checks
  - [ ] Return (is_valid, violation_reason)

- [ ] Integration tests:
  - [ ] Clarification flow: CLARIFICATION intent → LLM call → audit log
  - [ ] Limit exceeded: 3 clarifications → auto-skip
  - [ ] Policy validation: Violates policy → fallback response
  - [ ] Audit trail: Entries appear in submission.clarification_audit_log

### Phase 4: State Machine Integration (1-2 days)

- [ ] Update `ExchangeRepository.create_exchange()` to:
  - [ ] Accept intent_sequence
  - [ ] Set final_intent + final_intent_confidence
  - [ ] Initialize clarification_count

- [ ] Update `SubmissionRepository` to:
  - [ ] Track total_clarifications_requested
  - [ ] Track total_clarifications_granted
  - [ ] Append to clarification_audit_log

- [ ] Update [app/interview/realtime/](app/interview/realtime/) WebSocket to:
  - [ ] Emit clarification events
  - [ ] Handle replay question action
  - [ ] Handle auto-skip event

### Phase 5: Testing & Validation (2-3 days)

- [ ] Unit test suites:
  - [ ] Intent classification edge cases
  - [ ] Clarification validator all patterns
  - [ ] State machine transitions

- [ ] Integration test suite:
  - [ ] Full interview flow with 0 clarifications
  - [ ] Full interview flow with 1 clarification
  - [ ] Full interview flow with 3 clarifications
  - [ ] Auto-skip scenario (4th clarification attempt)
  - [ ] Policy violation scenario (hint detected)
  - [ ] ASR low confidence scenario

- [ ] Fairness test suite:
  - [ ] Two candidates, compare clarification counts
  - [ ] Audit log integrity
  - [ ] Field validation

---

## 💻 Code Templates

### Intent Classification Integration

```python
# In app/audio/ingestion/handler.py
async def process_candidate_speech(audio_bytes: bytes, submission_id: int):
    # Step 1: Transcribe
    transcript_result = await transcription_service.transcribe(audio_bytes)
    
    # Step 2: CLASSIFY INTENT (FIRST BUSINESS LOGIC)
    intent_result = await intent_classifier.classify(
        IntentClassificationRequest(
            transcript=transcript_result.transcript,
            confidence_score=transcript_result.confidence_score,
            question_context=await get_current_question(submission_id)
        )
    )
    
    # Step 3: Log immutably
    log_intent_classification(intent_result)
    
    # Step 4: Route to orchestration
    action = await orchestration_service.handle_candidate_input(
        submission_id=submission_id,
        intent=intent_result,
        transcript=transcript_result.transcript
    )
    
    return action
```

### Clarification Handler

```python
# In app/interview/orchestration/clarification_coordinator.py
async def handle_clarification_request(request: ClarificationRequest) -> dict:
    # Check limit
    if request.current_clarification_count >= 3:
        log_clarification_event(
            submission_id=request.submission_id,
            reason="CLARIFICATION_LIMIT_EXCEEDED"
        )
        return {
            "action": "auto_skip",
            "message": "Answer has been recorded. Moving to next question."
        }
    
    # Call LLM with strict policy
    response = await generate_clarification(
        ClarificationRequestContract(
            submission_id=request.submission_id,
            original_question=request.question_text,
            candidate_clarification_request=request.candidate_request,
            clarification_number=request.current_clarification_count + 1,
            constraints=ClarificationConstraints(
                max_words=120,
                allow_analogy=True,
                allow_hint=False
            )
        )
    )
    
    # Validate policy
    validator = ClarificationValidator()
    is_valid, reason = validator.validate(response, constraints)
    
    if not is_valid:
        log_policy_violation(reason)
        response.clarification_text = "I can't provide that clarification. Could you rephrase?"
    
    # Update submission
    submission = db.query(InterviewSubmission).get(request.submission_id)
    submission.total_clarifications_granted += 1
    submission.clarification_audit_log.append({
        "exchange_sequence": request.exchange_sequence,
        "question_id": request.question_id,
        "clarification_number": request.current_clarification_count + 1,
        "candidate_request": request.candidate_request,
        "llm_response": response.clarification_text,
        "timestamp": datetime.utcnow().isoformat()
    })
    db.commit()
    
    return {
        "action": "provide_clarification",
        "clarification_text": response.clarification_text,
        "new_clarification_count": request.current_clarification_count + 1,
        "replay_question": True
    }
```

### LLM Call (Temperature = 0)

```python
# In app/ai/llm/clarification.py
async def generate_clarification(
    request: ClarificationRequestContract
) -> ClarificationResponseContract:
    system_prompt = f"""
You are a clarification assistant for technical interviews.

ORIGINAL QUESTION:
{request.original_question}

CANDIDATE'S REQUEST:
{request.candidate_clarification_request}

---

YOU MAY:
- Rephrase the question
- Define terms
- Clarify constraints

YOU MUST NEVER:
- Suggest algorithms
- Suggest data structures
- Give hints
- Validate their attempt

Maximum 120 words. Natural language only.
"""
    
    response = await llm_provider.generate_text(
        prompt="",
        system=system_prompt,
        model="gpt-4o",
        temperature=0.0,  # ⭐ CRITICAL: DETERMINISTIC
        max_tokens=150,
        timeout_seconds=5
    )
    
    text = response.data.get('content', '').strip()
    word_count = len(text.split())
    
    result = ClarificationResponseContract(
        clarification_text=text,
        word_count=word_count,
        violates_policy=False,
        model_used=response.telemetry.model_id,
        temperature_used=0.0,
        telemetry=asdict(response.telemetry)
    )
    
    # Validate policy
    validator = ClarificationValidator()
    is_valid, reason = validator.validate(result, request.constraints)
    
    if not is_valid:
        result.violates_policy = True
        result.violation_reason = reason
        log_violation(reason)
    
    return result
```

---

## 🧪 Test Examples

### Test: Intent Classification

```python
async def test_intent_clarification():
    classifier = IntentClassifier()
    
    result = await classifier.classify(IntentClassificationRequest(
        transcript="What do you mean by optimal?",
        confidence_score=0.95,
        question_context="Design an optimal algorithm..."
    ))
    
    assert result.intent == "CLARIFICATION"
    assert result.confidence > 0.85
    assert result.contains_solution_attempt == False


async def test_intent_answer():
    classifier = IntentClassifier()
    
    result = await classifier.classify(IntentClassificationRequest(
        transcript="I would use dynamic programming with memoization",
        confidence_score=0.90,
        question_context="Design an algorithm..."
    ))
    
    assert result.intent == "ANSWER"
    assert result.contains_solution_attempt == True
```

### Test: Clarification Flow

```python
async def test_clarification_limit():
    # Simulate 3 clarifications
    request = ClarificationRequest(
        submission_id=1,
        current_clarification_count=3,
        question_text="...",
        candidate_request="..."
    )
    
    result = await handle_clarification_request(request)
    
    assert result["action"] == "auto_skip"
    assert "Moving to next question" in result["message"]


async def test_policy_validation():
    validator = ClarificationValidator()
    
    response = ClarificationResponseContract(
        clarification_text="You should use a hash table for efficiency",
        word_count=9,
        violates_policy=False,
        model_used="gpt-4o",
        temperature_used=0.0
    )
    
    is_valid, reason = validator.validate(response, ClarificationConstraints())
    
    assert is_valid == False
    assert "data_structure" in reason
```

---

## 📚 Key Files to Read

**In Order:**

1. [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md) - **START HERE**
2. [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md) - What changed
3. [app/interview/exchanges/REQUIREMENTS.md](app/interview/exchanges/REQUIREMENTS.md) - State machine
4. [app/audio/analysis/REQUIREMENTS.md](app/audio/analysis/REQUIREMENTS.md) - Intent classification
5. [app/interview/orchestration/REQUIREMENTS.md](app/interview/orchestration/REQUIREMENTS.md) - Orchestration
6. [app/ai/llm/REQUIREMENTS.md](app/ai/llm/REQUIREMENTS.md) - LLM contract
7. [app/interview/persistence/REQUIREMENTS.md](app/interview/persistence/REQUIREMENTS.md) - Data persistence

---

## ⚡ Quick Configuration

```yaml
# config/clarifications.yaml
clarifications:
  max_per_question: 3  # Hard limit
  llm_model: "gpt-4o"
  temperature: 0.0     # DETERMINISTIC only
  max_words: 120
  timeout_seconds: 5
  
policy:
  allow_analogy: true
  max_analogies_per_question: 1
  allow_hint: false    # RECOMMEND: false for fairness
  max_hints: 0
  
  prohibitions:
    - algorithm
    - dynamic programming
    - recursion
    - hash table
    - # ... more
    
asr:
  confidence_threshold: 0.70  # Below this → ask repeat
  
audit:
  enable_logging: true         # Always true
  log_location: "database"     # Or "file"
```

---

## 🎯 Success Criteria

- [ ] Intent classification <500ms p95  
- [ ] Clarification generation <5s p95
- [ ] No policy violations in production logs  
- [ ] All candidates have < 10% variance in clarification counts  
- [ ] Audit logs show complete intent progression  
- [ ] Auto-skip triggers correctly at count=3
- [ ] Zero hints/algorithms in production clarifications

---

## 🆘 Troubleshooting

### Issue: Intent classified as CLARIFICATION but no LLM call

**Cause:** Orchestration not routing CLARIFICATION intents correctly.  
**Fix:** Check `handle_candidate_input()` routing logic.

### Issue: Same input produces different intents

**Cause:** temperature != 0 in intent classifier.  
**Fix:** Verify `IntentClassifier` temperature=0 (if using LLM) or uses pure NLP rules.

### Issue: LLM responding with hints despite policy

**Cause:** Policy validator not running or regex patterns too lenient.  
**Fix:** Run validator on all responses before exposure; review prohibited pattern list.

### Issue: Clarification count not incrementing

**Cause:** Submission not being updated in database.  
**Fix:** Ensure `db.commit()` after updating `total_clarifications_granted`.

### Issue: Audit log entries missing

**Cause:** Logging not called or database append failing.  
**Fix:** Add logging calls everywhere clarifications handled; test append to JSONB.

---

**Ready to implement?** Start with Phase 1 (Data Model) and work through sequentially. Good luck! 🚀
