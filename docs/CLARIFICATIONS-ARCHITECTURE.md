# AI Interviewer Clarification Architecture
## High-Integrity Intent Classification & Bounded Clarifications

**Document Status:** CANONICAL | **Version:** 1.0 | **Last Updated:** Feb 17, 2026

---

## Executive Summary

This document formalizes the **high-integrity clarification architecture** for the AI Interviewer system:

✔ **Max 3 clarifications per question** → Auto-skip if exceeded  
✔ **Deterministic intent classification** (temperature=0) → Runs FIRST before any business logic  
✔ **Strict LLM clarification contract** → No hints drift, no algorithm suggestions  
✔ **Immutable audit logging** → Every interaction recorded for defense  
✔ **Fair fairness tracking** → All candidates get consistent treatment  

---

## 🎯 Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Max 3 clarifications** | Prevents infinite questioning; fair time usage |
| **Auto-skip on limit exceeded** | No emotional explanation; neutral system response |
| **Intent classification FIRST** | No business logic until intent determined |
| **Temperature = 0 LLM calls** | Deterministic; reproducible; fair across candidates |
| **Strict prohibition list** | No algorithm/hint drift via creative prompting |
| **Immutable logging** | Audit trail for fairness challenges; candidate defense |
| **Fairness tracking in submission** | Detect bias; compare similar candidates |

---

## 🏗️ Architecture Layers

### Layer 1: Intent Classification (Audio Analysis)

**Module:** `app/audio/analysis/REQUIREMENTS.md`

Every candidate utterance classified **deterministically** BEFORE any other processing:

```
Utterance → ASR (Confidence score)
         → Intent Classifier (temperature=0)
         → Immutable Log
         → State Machine Route
```

**Intent Types:**
- `ANSWER` - Solution logic detected
- `CLARIFICATION` - Question about wording/terms  
- `REPEAT` - Request to hear question again
- `POST_ANSWER` - Speech after submission (rejected)
- `INVALID` - Silence, noise, unintelligible
- `INCOMPLETE` - Fragment, more to come
- `UNKNOWN` - Ambiguous

**Critical Rule:** Default to ANSWER if ambiguous (conservative).

---

### Layer 2: Clarification Coordination (Orchestration)

**Module:** `app/interview/orchestration/REQUIREMENTS.md`

Routes intent classifications to appropriate handlers:

**If intent = CLARIFICATION:**
1. Check `clarification_count < 3`
2. If `>= 3`: Auto-skip, log reason, return neutral message
3. Else: Call LLM with strict constraints
4. Increment counter in submission
5. Log clarification immutably
6. Replay question

**If intent = ANSWER:**  
→ Process response submission

**If intent = POST_ANSWER:**  
→ Reject with "Answer recorded. Moving to next question."

**If intent = INVALID/ASR_UNCERTAINTY:**  
→ Ask for repeat

---

### Layer 3: LLM Clarification Contract (AI/LLM)

**Module:** `app/ai/llm/REQUIREMENTS.md`

**Strict System Prompt Constraints:**

```
✓ ALLOWED: Rephrase, define terms, restate constraints, 1 abstract analogy
✗ FORBIDDEN: Algorithms, data structures, hints, validation, encouragement
```

**Response Validation:**
- Word count ≤ 120
- No prohibited patterns detected
- Policy validator runs on all responses
- Policy violations logged for audit

**Temperature = 0:** Ensures deterministic, reproducible output.

---

### Layer 4: State Machine & Immutable Exchange

**Module:** `app/interview/exchanges/REQUIREMENTS.md`

**Question State Machine:**

```
ASKED
  ↓
WAITING_INPUT
  ├→ CLARIFICATION_REQUESTED (max 3x)
  │   ↓
  │   WAITING_INPUT (loop)
  └→ ANSWER_SUBMITTED
      ↓
      POST_ANSWER_WINDOW (protect against modification)
      ↓
      EVALUATED
      ↓
      NEXT_QUESTION
```

**New Exchange Fields:**
- `clarification_count` - How many clarifications given (0-3)
- `clarification_limit_exceeded` - Boolean flag
- `intent_sequence` - JSONB array of all intents in order
- `final_intent` - Last classification (for audit)

---

### Layer 5: Persistence & Audit Logging

**Module:** `app/interview/persistence/REQUIREMENTS.md`

**Submission-Level Tracking:**
- `total_clarifications_requested` - How many times candidate asked
- `total_clarifications_granted` - How many accepted
- `total_auto_skips_due_to_clarification` - Auto-skips from limit
- `clarification_audit_log` - JSONB array of all events

**Why:** Fairness analysis, bias detection, candidate defense.

---

## 📊 Data Flow Example

```
Candidate speaks: "What algorithm should I use?"

1. TRANSCRIPTION
   Input: Audio bytes
   Output: transcript="What algorithm should I use?", confidence=0.92

2. INTENT CLASSIFICATION
   Input: transcript, confidence, question_context
   Classifier rules:
     - Contains "algorithm" keyword
     - No solution logic detected
     - Question mark indicates asking for help
   Output: intent=CLARIFICATION, confidence=0.95

3. ORCHESTRATION ROUTE
   Input: intent=CLARIFICATION, current_clarif_count=0
   Check: clarif_count < 3? YES
   Output: route to clarification_handler

4. CLARIFICATION LLM CALL
   Input: 
     - original_question="Design an algorithm to find..."
     - candidate_request="What algorithm should I use?"
     - constraints={ max_words: 120, prohibitions: [...] }
     - temperature: 0.0
   Output: 
     - "I can't suggest algorithms. Can you describe your approach?"
   Validation: Passes policy (no prohibited patterns)

5. IMMUTABLE LOGGING
   Log entry created:
     - exchange: 5
     - clarification_number: 1
     - candidate_request: "What algorithm should I use?"
     - llm_response: "I can't suggest..."
     - timestamp: 2026-02-17T10:45:23.123Z

6. SUBMISSION UPDATE
   submission.total_clarifications_granted += 1
   submission.clarification_audit_log.append(log_entry)

7. RESPONSE TO CLIENT
   Message: "I can't suggest algorithms. Can you describe your approach?"
   Action: Replay question
```

---

## 🛡️ Fairness & Audit Trail

### Fairness Tracking

**Question-Level:**
```json
{
  "question_id": 101,
  "clarification_count": 2,
  "hint_given": false,
  "auto_skipped": false,
  "final_intent_sequence": [
    {"intent": "CLARIFICATION", "confidence": 0.95},
    {"intent": "CLARIFICATION", "confidence": 0.92},
    {"intent": "ANSWER", "confidence": 0.88}
  ]
}
```

**Submission-Level:**
```json
{
  "submission_id": 1000,
  "candidate_id": 456,
  "total_clarifications_requested": 25,
  "total_clarifications_granted": 5,
  "total_auto_skips_due_to_clarification": 2,
  "fairness_score": {
    "clarification_equity": "fair",  // Similar candidates got similar #
    "hint_given_equity": "fair"      // Either all or none got hints
  }
}
```

### Audit Trail Query

**Defense scenario:** "My interview was unfair. I got auto-skipped on a question."

```sql
SELECT 
    e.sequence_order,
    e.question_id,
    e.clarification_count,
    e.clarification_limit_exceeded,
    e.intent_sequence,
    s.total_clarifications_granted
FROM interview_exchanges e
JOIN interview_submissions s ON e.interview_submission_id = s.id
WHERE s.candidate_id = 456
  AND e.clarification_limit_exceeded = true;
```

Returns: Complete audit trail of clarifications + intents.

---

## ⚠️ Risk Mitigation

### Risk 1: LLM Hint Drift

**Problem:** "Let me provide one subtle hint..."

**Mitigation:**
- Strict prohibition list in system prompt
- Post-generation validation with regex patterns
- Policy violations logged
- Fallback safe response if violated

### Risk 2: Fairness Violation

**Problem:** Candidate A gets hints, Candidate B doesn't.

**Mitigation:**
- Define hint policy globally (allow 0 or 1 per question, consistent)
- Log `hint_given` boolean
- Fairness score aggregation across candidates
- Alert if variance detected

### Risk 3: ASR Misclassification

**Problem:** "I think maybe we can use recursion" → ASR error → wrong intent.

**Mitigation:**
- ASR confidence threshold (0.70)
- If below threshold: Ask candidate to repeat
- Immutable log of confidence scores
- Re-run classification on repeat

### Risk 4: Infinite Clarifications

**Problem:** Candidate keeps asking; interview never ends.

**Mitigation:**
- Hard limit: 3 clarifications max
- Auto-skip with neutral message ("Answer recorded")
- No emotional language
- Log reason: CLARIFICATION_LIMIT_EXCEEDED

---

## 📋 Implementation Checklist

### Code Changes Required

- [ ] Update `app/audio/analysis/` - Add Intent Classifier
- [ ] Update `app/interview/exchanges/` - Add clarification_count, intent_sequence to schema
- [ ] Update `app/interview/persistence/` - Add submission-level clarification tracking
- [ ] Update `app/interview/orchestration/` - Add clarification coordinator
- [ ] Update `app/interview/realtime/` - WebSocket events for clarification flow
- [ ] Update `app/ai/llm/` - Implement ClarificationValidator, temperature=0 calls
- [ ] Update `app/interview/api/` - Expose clarification audit in GET endpoints
- [ ] Create migration: Add new columns to interview_submissions, interview_exchanges
- [ ] Create tests: Intent classification, clarification flow, auto-skip, audit logging

### Configuration Required

- [ ] Intent classifier model selection (rule-based NLP or temperature=0 LLM)
- [ ] Clarification LLM model (recommend: gpt-4o)
- [ ] Clarification max words (120 recommended)
- [ ] Clarification allow_hint (recommend: false)
- [ ] Enable fairness tracking (boolean config)
- [ ] Set ASR confidence threshold (0.70 recommended)

---

## 📚 Module References

All modules reference this architecture:

- [app/interview/exchanges/REQUIREMENTS.md](../app/interview/exchanges/REQUIREMENTS.md) - State machine + immutable exchange
- [app/audio/analysis/REQUIREMENTS.md](../app/audio/analysis/REQUIREMENTS.md) - Intent classification
- [app/interview/orchestration/REQUIREMENTS.md](../app/interview/orchestration/REQUIREMENTS.md) - Clarification coordinator
- [app/ai/llm/REQUIREMENTS.md](../app/ai/llm/REQUIREMENTS.md) - LLM clarification contract
- [app/interview/persistence/REQUIREMENTS.md](../app/interview/persistence/REQUIREMENTS.md) - Audit logging

---

## 🎓 Design Principles

1. **Fair:** All candidates treated consistently, no hidden logic
2. **Auditable:** Every interaction logged immutably
3. **Safe:** LLM cannot drift into giving hints or solutions
4. **Fast:** Intent classification <500ms, clarification <5s
5. **Deterministic:** Same input → same output (temperature=0)
6. **Honest:** No emotional language, neutral system responses
7. **Defensive:** Complete audit trail for fairness challenges

---

## 🔮 Future Enhancements

1. **Candidate-Specific Thresholds**: Adjust max_clarifications based on role difficulty
2. **Domain-Specific Classifiers**: Specialized intent models per question type
3. **Multimodal Input**: Consider candidate facial expressions for incomplete detection
4. **Historical Patterns**: Flag candidates with unusual clarification patterns for review
5. **Adaptive Hints Policy**: Adjust hint allowance based on role level

---

**Document Owners:** Architecture Team  
**Last Reviewed:** Feb 17, 2026  
**Next Review:** 3 months
