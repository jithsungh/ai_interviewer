# Frontend Integration Guide: Practice Session Behavior

## Issue Summary

~~When starting a practice interview session, the interview immediately completes if there are no questions available in the database for the selected template.~~

**FIXED:** Backend now prevents starting practice sessions with zero questions and returns a clear error message.

## Root Cause (Historical)

### Previous Behavior (Before Fix)

1. **Template Snapshot Creation** ([repository.py#L818-L938](app/candidate/persistence/repository.py))
   - When a practice session starts, the system creates a "snapshot" of questions based on the template configuration
   - It queries the database for questions matching the template's requirements (coding problems, technical questions, behavioral questions, etc.)
   - If **no questions are found**, it creates an empty snapshot with `total_questions: 0` and `sections: []`

2. **WebSocket Connection** ([routes.py#L315-L320](app/interview/realtime/api/routes.py))
   - Client connects to `/ws/interview/{submission_id}?token=<JWT>`
   - Client sends `join_session` event
   - Client sends `request_next_question` event

3. **Question Resolution** ([question_sequencer.py#L68-L96](app/interview/orchestration/question_sequencer.py))
   - Backend checks if `current_sequence >= total_questions`
   - When `total_questions = 0`, condition is `0 >= 0` = **True**
   - Returns `None` (no more questions)

4. **Completion Event** ([event_handler.py#L186-L201](app/interview/realtime/domain/event_handler.py))
   - When `resolve_next_question()` returns `None`, backend sends `interview_completed` event
   - This happens **immediately** on the first `request_next_question` call

### Why Templates Have No Questions

Common scenarios:
- Database has no active coding problems (`coding_problems.is_active = true`)
- Template configured topics don't match any questions in database
- Questions exist but are marked inactive or filtered out by template criteria
- Template's `section_sequence` references non-existent question pools

### Section Ordering Issue

Previously, coding questions appeared first because:
- Template's `interview_structure.section_sequence` listed `"coding_round"` before other sections
- Question snapshot builder processes sections in this order
- First available section becomes first in sequence

Example template structure:
```json
{
  "interview_structure": {
    "section_sequence": ["coding_round", "technical", "behavioral"]
  },
  "coding_round": {"enabled": true, "total_problems": 2},
  "technical": {"enabled": true, "question_count": 5}
}
```

If coding problems exist but technical questions don't, you'd get only coding questions first.

## WebSocket Event Reference

### interviewer_completed Event

Sent when interview has no more questions (or never had any).

```json
{
  "event_type": "interview_completed",
  "submission_id": 123,
  "completion_reason": "all_questions_answered",
  "submitted_at": "2026-03-09T10:30:00Z",
  "exchanges_completed": 0,
  "total_questions": 0,
  "message": "Interview completed successfully!",
  "next_steps": "Results will be available within 24 hours."
}
```

**Key fields for detection:**
- `exchanges_completed: 0` - No questions were answered
- `total_questions: 0` - No questions were available
- `completion_reason: "all_questions_answered"` - Technically true but misleading

## Frontend Implementation Guide

### 1. Handle Practice Start Error

**When:** Calling `POST /api/v1/candidate/practice/start`

**Error to catch:**
```javascript
try {
  const response = await fetch('/api/v1/candidate/practice/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      template_id: selectedTemplateId,
      experience_level: 'entry',
      voice_interview: false
    })
  });

  if (!response.ok) {
    const error = await response.json();
    
    // Check for no questions error
    if (error.message?.includes('no available questions')) {
      showNoQuestionsError(error.message);
      return;
    }
    
    throw new Error(error.message);
  }

  const { submission_id } = await response.json();
  // Proceed to WebSocket connection
  startWebSocketSession(submission_id);

} catch (error) {
  handleStartError(error);
}
```

### 2. Show Appropriate User Message

**DON'T show:** "Interview completed successfully!" (misleading)

**DO show:**

```
❌ No Questions Available

This practice template currently has no questions in the database.

Possible reasons:
• No coding problems have been imported yet
• Questions for this template's topics are not available
• All questions are marked as inactive

What to do:
• Try a different practice template
• Contact support if this persists
• Check back later when questions are added

[Try Another Template] [Go to Dashboard]
```

### 3. Template Selection UI Enhancement

**Before starting a session**, display available question count:

```javascript
// GET /api/v1/candidate/practice/templates response should include:
{
  "templates": [
    {
      "id": 1,
      "name": "DSA Fundamentals",
      "available_questions": 0,  // ← Add this field
      "sections": {...}
    }
  ]
}
```

**UI indication:**
```
┌─────────────────────────────────────┐
│ DSA Fundamentals                     │
│ Data structures and algorithms       │
│                                      │
│ ⚠️  0 questions available            │
│ [Disabled Button]                    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Frontend Development                 │
│ React, TypeScript, HTML/CSS          │
│                                      │
│ ✓ 12 questions available             │
│ [Start Practice]                     │
└─────────────────────────────────────┘
```

### 4. Recommended Request Flow

```javascript
class PracticeInterviewManager {
  async startPractice(templateId, options) {
    try {
      // Step 1: Create practice submission
      const response = await fetch('/api/v1/candidate/practice/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.token}`
        },
        body: JSON.stringify({
          template_id: templateId,
          experience_level: options.experienceLevel,
          voice_interview: options.voiceInterview,
          video_recording: options.videoRecording,
          ai_proctoring: options.aiProctoring
        })
      });

      if (!response.ok) {
        const error = await response.json();
        
        // Handle no questions error specifically
        if (error.message?.includes('no available questions')) {
          this.showNoQuestionsModal({
            templateName: this.getTemplateName(templateId),
            message: error.message
          });
          return null;
        }
        
        throw new Error(error.message || 'Failed to start practice session');
      }

      const { submission_id } = await response.json();

      // Step 2: Connect to WebSocket (only if step 1 succeeded)
      const ws = new PracticeWebSocket(submission_id, this.token);
      await ws.connect();
      
      return ws;

    } catch (error) {
      this.handleError(error);
      return null;
    }
  }

  showNoQuestionsModal({ templateName, message }) {
    // Show user-friendly error modal
    modal.show({
      title: '❌ No Questions Available',
      message: `
        Cannot start practice for "${templateName}".
        
        ${message}
        
        Please try a different practice template or contact support.
      `,
      actions: [
        { label: 'Try Another Template', onClick: () => this.showTemplateSelector() },
        { label: 'Go to Dashboard', onClick: () => this.goToDashboard() }
      ]
    });
  }
}
```

### 5. WebSocket Event Handling (Standard Flow)

Since empty templates are now prevented at the start endpoint, WebSocket handling is standard:

```javascript
class PracticeWebSocket {
  async connect() {
    this.ws = new WebSocket(`/ws/interview/${this.submissionId}?token=${this.token}`);
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleEvent(data);
    };

    await this.sendEvent({ event_type: 'join_session' });
    await this.sendEvent({ event_type: 'request_next_question' });
  }

  handleEvent(event) {
    switch (event.event_type) {
      case 'question_payload':
        this.showQuestion(event);
        break;

      case 'interview_completed':
        // No need to check for empty interview - backend prevents it
        this.showCompletionSuccess(event);
        break;

      case 'error':
        this.handleError(event);
        break;
    }
  }
}
```

## Backend Changes Made

### Files Modified

1. **[app/candidate/persistence/repository.py](app/candidate/persistence/repository.py#L820-L825)**
   - **Added:** Validation to prevent starting practice sessions with 0 questions
   - **Raises:** `ValueError` with clear message if template has no available questions
   - **Message:** "Cannot start practice session: Template '{name}' has no available questions. Please ensure the database has active questions for the configured sections, or try a different template."

2. **[app/interview/orchestration/contracts.py](app/interview/orchestration/contracts.py#L60-L72)**
   - **Restored:** Strict validation requiring at least 1 section and total_questions > 0
   - **Prevents:** Empty template snapshots from being created

### Current Behavior (After Fix)

**POST /api/v1/candidate/practice/start**

When requesting a template with no questions:

```http
POST /api/v1/candidate/practice/start
Content-Type: application/json

{
  "template_id": 1,
  "experience_level": "entry",
  "voice_interview": false
}
```

**Response (400 Bad Request):**
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Cannot start practice session: Template 'DSA Fundamentals' has no available questions. Please ensure the database has active questions for the configured sections, or try a different template.",
  "details": null
}
```

### Why These Changes Were Made

Instead of allowing empty templates to proceed (causing immediate completion), the backend now:
1. **Validates early** - Checks question availability before creating the interview submission
2. **Fails fast** - Returns clear error during the POST request, not during WebSocket connection
3. **Better UX** - Frontend can show error immediately without establishing WebSocket connection
4. **Clear messaging** - Error message guides user to try different template or contact support

## Testing Checklist

- [ ] Attempting to start practice with empty template returns **400 error** (not 200)
- [ ] Error response includes clear message about "no available questions"
- [ ] Frontend shows error modal/message (not "loading..." indefinitely)
- [ ] Error modal offers "Try Another Template" action
- [ ] WebSocket connection is **not attempted** when start fails
- [ ] Templates with 0 questions are disabled in template selector (optional enhancement)
- [ ] Template list shows question count (optional enhancement)
- [ ] Normal practice flow (with questions) still works correctly
- [ ] `interview_completed` event only happens after answering actual questions
- [ ] Error doesn't prevent trying other templates

## API Endpoint to Check Question Availability

**Recommendation:** Add question count to template list endpoint

```http
GET /api/v1/candidate/practice/templates
```

**Current response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "DSA Fundamentals",
      "description": "...",
      "template_structure": {...}
    }
  ]
}
```

**Suggested enhancement:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "DSA Fundamentals", 
      "description": "...",
      "template_structure": {...},
      "available_questions": 0,  // ← Add this
      "sections_summary": {      // ← Optional: breakdown by section
        "coding": 0,
        "technical": 0,
        "behavioral": 0
      }
    }
  ]
}
```

This allows frontend to:
1. Disable templates with 0 questions
2. Show helpful warnings before starting
3. Prevent wasted API calls and poor UX

## Database Requirements

For templates to have questions, ensure:

### Coding Problems
```sql
-- Check active coding problems
SELECT difficulty, COUNT(*) 
FROM coding_problems 
WHERE is_active = true AND pipeline_status = 'imported'
GROUP BY difficulty;
```

### Technical Questions
```sql
-- Check active questions by type
SELECT question_type, difficulty_level, COUNT(*)
FROM questions
WHERE is_active = true
GROUP BY question_type, difficulty_level;
```

### Topics
```sql
-- Check questions linked to topics
SELECT t.name, COUNT(q.id) as question_count
FROM topics t
LEFT JOIN questions q ON q.topic_id = t.id AND q.is_active = true
GROUP BY t.id, t.name;
```

## Summary

**What happens now (FIXED):**
1. Frontend calls `POST /api/v1/candidate/practice/start` with template_id
2. Backend validates template has at least 1 question
3. If 0 questions: Returns **400 error** with clear message
4. If questions exist: Creates submission and returns `submission_id`
5. Frontend connects to WebSocket only if step 4 succeeded

**What frontend should do:**
1. **Handle 400 error** from `/api/v1/candidate/practice/start` endpoint
2. Check if error message contains "no available questions"  
3. Show error modal explaining the issue (see message template above)
4. Don't attempt WebSocket connection if start failed
5. Offer action to try different template
6. **(Optional but recommended)** Show question counts before template selection

**What backend does:**
- **Prevents** empty practice sessions from being created
- Returns **400 Bad Request** at the start endpoint (before WebSocket)
- Provides clear error message explaining the issue
- Ensures all created practice sessions have at least 1 question

**Key improvement:**
- **Before:** Empty interview would complete immediately in WebSocket, confusing experience
- **After:** Clear error at session start, before any WebSocket connection
- **Result:** Better UX, clearer error handling, no "completed successfully" with 0 questions
