# 🎯 AI Interviewer: High-Integrity Clarifications Architecture

## 📚 Core Documentation

### Entry Points (Choose Your Path)

**👨‍💼 I'm a manager/architect:**  
→ Start: [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md)  
Read time: 15 minutes | Contains: Executive summary, design decisions, fairness model

**👨‍💻 I'm implementing this:**  
→ Start: [QUICK-START.md](QUICK-START.md)  
Read time: 10 minutes | Contains: Implementation checklist, code templates, test examples

**📊 I want to see what changed:**  
→ Start: [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md)  
Read time: 20 minutes | Contains: All changes, data model, patterns, risk mitigations

**📋 I need a file list:**  
→ Start: [MODIFIED-FILES.md](MODIFIED-FILES.md)  
Read time: 5 minutes | Contains: Files changed, statistics, cross-references

---

## 🚀 Quick Summary: What Was Done

### ✅ Requirements Formalized

| Requirement | Status | Location |
|-------------|--------|----------|
| **Max clarifications = 3** | ✅ Defined | [app/interview/exchanges/REQUIREMENTS.md](app/interview/exchanges/REQUIREMENTS.md#section-4) |
| **Auto-skip on limit exceeded** | ✅ Defined | [app/interview/orchestration/REQUIREMENTS.md](app/interview/orchestration/REQUIREMENTS.md#section-3a) |
| **Intent classification (temperature=0)** | ✅ Defined | [app/audio/analysis/REQUIREMENTS.md](app/audio/analysis/REQUIREMENTS.md#section-5a) |
| **Strict clarification policy** | ✅ Defined | [app/ai/llm/REQUIREMENTS.md](app/ai/llm/REQUIREMENTS.md#section-4) |
| **Immutable audit logging** | ✅ Defined | [app/interview/exchanges/REQUIREMENTS.md](app/interview/exchanges/REQUIREMENTS.md#section-5) |
| **Fairness tracking** | ✅ Defined | [app/interview/persistence/REQUIREMENTS.md](app/interview/persistence/REQUIREMENTS.md#section-2a) |
| **ASR confidence handling** | ✅ Defined | [app/audio/analysis/REQUIREMENTS.md](app/audio/analysis/REQUIREMENTS.md#section-5a) |

### ✅ Documentation Created

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md) | High-level overview, data flow, fairness model | 15 min |
| [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md) | What changed, why, implementation impact | 20 min |
| [QUICK-START.md](QUICK-START.md) | Developer implementation guide with code | 10 min |
| [MODIFIED-FILES.md](MODIFIED-FILES.md) | Files changed, statistics, cross-references | 5 min |

### ✅ REQUIREMENTS.md Updated

| Module | Sections Added | Impact |
|--------|----------------|--------|
| [app/interview/exchanges/REQUIREMENTS.md](app/interview/exchanges/REQUIREMENTS.md) | Intent taxonomy, state machine, audit policy | Core +450 lines |
| [app/audio/analysis/REQUIREMENTS.md](app/audio/analysis/REQUIREMENTS.md) | Intent classification | Core +350 lines |
| [app/interview/orchestration/REQUIREMENTS.md](app/interview/orchestration/REQUIREMENTS.md) | Clarification coordinator | Core +400 lines |
| [app/interview/persistence/REQUIREMENTS.md](app/interview/persistence/REQUIREMENTS.md) | Audit logging schema | Core +60 lines |
| [app/ai/llm/REQUIREMENTS.md](app/ai/llm/REQUIREMENTS.md) | Clarification contract | Core +380 lines |

---

## 🧠 Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│  CANDIDATE SPEECH → TRANSCRIBED TEXT + ASR CONFIDENCE           │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│  INTENT CLASSIFICATION (temperature=0, deterministic)            │
│  - ANSWER | CLARIFICATION | REPEAT | INVALID | etc.             │
│  - Logged immutably FIRST (no business logic before this)        │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
            ┌────────┴────────┐
            ↓                 ↓
     ANSWER ✓      CLARIFICATION?
        │            │
        │        If count < 3:
        │            ↓
        │      LLM Response (temp=0)
        │            ↓
        │      Policy Validator
        │            ↓
        │      Increment Count
        │      Log to Audit Trail
        │      Replay Question
        │            ↓
        │      Loop back (wait)
        ↓            ↓
     Create        If count >= 3:
     Exchange        ↓
        │      Auto-skip (neutral)
        │      Mark reason in log
        ↓            ↓
    Evaluate    NEXT_QUESTION
```

---

## 📊 Key Design Points

### 1. Intent Classification First

```
▌ NO business logic until intent determined
▌ Deterministic (temperature=0)
▌ Rule-based NLP or strict LLM
▌ Immutably logged for audit
```

### 2. Max 3 Clarifications (Hard Limit)

```
Request 1 ✓ (count=1)
Request 2 ✓ (count=2)  
Request 3 ✓ (count=3)
Request 4 ✗ → Auto-skip (neutral message)
```

### 3. Strict Clarification Policy

```
ALLOWED:
  ✓ Rephrase question
  ✓ Define terms
  ✓ Clarify constraints
  ✓ 1 abstract analogy max

FORBIDDEN:
  ✗ Algorithm suggestions
  ✗ Data structure suggestions
  ✗ Hints
  ✗ Validation ("you're right")
  ✗ Encouragement
```

### 4. Fairness Tracking

```
Per-Submission:
  - total_clarifications_requested
  - total_clarifications_granted
  - total_auto_skips_due_to_clarification
  
Enables: Compare across candidates → detect bias
```

---

## 🔗 Module Dependencies

```
┌─────────────────────────────────────┐
│  app/audio/analysis                 │
│  (Intent Classifier)                │
└──────────────────┬──────────────────┘
                   │
                   ↓
┌─────────────────────────────────────┐
│  app/interview/orchestration        │
│  (Clarification Coordinator)        │
└──────────┬──────────────┬───────────┘
           │              │
      ┌────↓─────┐    ┌───↓──────────┐
      ↓          ↓    ↓              ↓
    ai/llm   persistence      exchanges
    (Policy  (Audit Log)      (Exchange)
     Valid)
```

---

## 📈 Implementation Timeline

| Phase | Task | Duration | Type |
|-------|------|----------|------|
| **1** | Data model migrations | 1-2 days | Database |
| **2** | Intent classification | 2-3 days | Code |
| **3** | Clarification handler | 2-3 days | Code |  
| **4** | State machine integration | 1-2 days | Code |
| **5** | Testing & validation | 2-3 days | QA |
| | **Total** | **~9-14 days** | |

See [QUICK-START.md](QUICK-START.md) for detailed checklist.

---

## ✨ Key Principles

1. **Fair** - All candidates treated consistently
2. **Auditable** - Every interaction logged immutably
3. **Safe** - Policy prevents LLM hint drift
4. **Fast** - Intent <500ms, clarification <5s
5. **Deterministic** - Same input → same output (temperature=0)
6. **Honest** - Neutral language, no encouragement
7. **Defensive** - Complete audit for fairness challenges

---

## 🎓 What Each Document Covers

### docs/CLARIFICATIONS-ARCHITECTURE.md
- **Level:** High-level overview
- **Audience:** Architects, leads, technical stakeholders
- **Length:** ~30 minutes read
- **Covers:**
  - Executive summary (key decisions)
  - 5-layer architecture
  - Data flow examples
  - Fairness model
  - Risk mitigations
  - Implementation checklist

### UPDATES-SUMMARY.md
- **Level:** Implementation overview
- **Audience:** Developers, QA engineers
- **Length:** ~30 minutes read
- **Covers:**
  - All REQUIREMENTS changes (section-by-section)
  - New dataclasses/contracts
  - Data model changes
  - Code patterns
  - Risk mitigations
  - Acceptance criteria achieved

### QUICK-START.md
- **Level:** Implementation guide
- **Audience:** Developers starting implementation
- **Length:** ~15 minutes read + development time
- **Covers:**
  - 30-second pitch
  - 5-phase checklist with details
  - Code templates
  - Test examples
  - Configuration
  - Troubleshooting

### MODIFIED-FILES.md
- **Level:** Change summary
- **Audience:** Anyone tracking changes
- **Length:** ~5 minutes read
- **Covers:**
  - All modified files
  - All created documents
  - Statistics (lines, dataclasses, etc.)
  - Cross-references
  - Implementation path

---

## 🚀 How to Use These Documents

### Scenario 1: "I need to understand the architecture"
→ [QUICK-START.md](QUICK-START.md) (5 min) → [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md) (15 min)

### Scenario 2: "I'm implementing this"
→ [QUICK-START.md](QUICK-START.md) → Follow checklist → Reference REQUIREMENTS files

### Scenario 3: "What changed exactly?"
→ [MODIFIED-FILES.md](MODIFIED-FILES.md) (5 min) → [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md) (optional deep dive)

### Scenario 4: "I need specific implementation details"
→ [UPDATED REQUIREMENTS.md](app/interview/exchanges/REQUIREMENTS.md) (and others)

---

## 📞 Quick Reference: Where to Find Things

| Question | Answer Location |
|----------|-----------------|
| What is the max clarifications? | [§4 exchanges REQUIREMENTS](app/interview/exchanges/REQUIREMENTS.md#section-4) |
| How does intent classification work? | [§5a audio/analysis REQUIREMENTS](app/audio/analysis/REQUIREMENTS.md#section-5a) |
| What LLM calls are allowed? | [§4 ai/llm REQUIREMENTS](app/ai/llm/REQUIREMENTS.md#section-4) |
| What fields to add to database? | [UPDATES-SUMMARY.md - Data Model](UPDATES-SUMMARY.md#data-model-changes) or [§2a persistence](app/interview/persistence/REQUIREMENTS.md#section-2a) |
| How do I implement this? | [QUICK-START.md](QUICK-START.md) |
| What changed and why? | [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md) |
| File list and statistics | [MODIFIED-FILES.md](MODIFIED-FILES.md) |

---

## ✅ Verification Checklist

### Architecture Documented?
- ✅ [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md)

### All Changes Summarized?
- ✅ [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md)

### Implementation Guide Created?
- ✅ [QUICK-START.md](QUICK-START.md)

### All REQUIREMENTS Updated?
- ✅ [app/interview/exchanges/REQUIREMENTS.md](app/interview/exchanges/REQUIREMENTS.md)
- ✅ [app/audio/analysis/REQUIREMENTS.md](app/audio/analysis/REQUIREMENTS.md)
- ✅ [app/interview/orchestration/REQUIREMENTS.md](app/interview/orchestration/REQUIREMENTS.md)
- ✅ [app/interview/persistence/REQUIREMENTS.md](app/interview/persistence/REQUIREMENTS.md)
- ✅ [app/ai/llm/REQUIREMENTS.md](app/ai/llm/REQUIREMENTS.md)

### Cross-References Added?
- ✅ All 6 key modules reference master architecture doc

---

## 🎯 Next Steps

**Immediate (Ready Now):**
1. Read [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md)
2. Read [QUICK-START.md](QUICK-START.md)
3. Review relevant REQUIREMENTS.md sections

**Short Term (This Sprint):**
1. Phase 1: Database migrations
2. Phase 2: Intent classification code

**Medium Term (Next Sprint):**
1. Phase 3: Clarification handler
2. Phase 4: State machine integration
3. Phase 5: Testing

---

## 📞 Document Status

| Document | Last Updated | Status | Version |
|----------|--------------|--------|---------|
| [docs/CLARIFICATIONS-ARCHITECTURE.md](docs/CLARIFICATIONS-ARCHITECTURE.md) | Feb 17, 2026 | ✅ Complete | 1.0 |
| [UPDATES-SUMMARY.md](UPDATES-SUMMARY.md) | Feb 17, 2026 | ✅ Complete | 1.0 |
| [QUICK-START.md](QUICK-START.md) | Feb 17, 2026 | ✅ Complete | 1.0 |
| [MODIFIED-FILES.md](MODIFIED-FILES.md) | Feb 17, 2026 | ✅ Complete | 1.0 |
| All REQUIREMENTS.md | Feb 17, 2026 | ✅ Updated | 2.0 |

---

## 🎓 Summary

**What:** Formalized high-integrity intent classification & clarification architecture  
**Why:** Ensure fair, auditable, safe interview clarifications with hard limits & audit trails  
**How:** 5 layers (intent → routing → clarification → exchange → audit) with strict policy validation  
**Status:** ✅ All specifications complete, ready for code implementation  
**Next:** Follow [QUICK-START.md](QUICK-START.md) implementation guide  

---

**Questions?** Refer to the appropriate document above. All architectural decisions are documented.

**Ready to code?** Start with [QUICK-START.md](QUICK-START.md) Phase 1.

---

*Last Updated: February 17, 2026*  
*Architecture Team*  
*Status: ✅ RELEASE READY*
