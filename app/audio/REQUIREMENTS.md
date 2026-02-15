# Audio Module Requirements

## 1. Purpose

The audio module provides **structured audio analytics signal generation** for voice-based interviews.

**Core Responsibilities:**

- Real-time speech stream ingestion and normalization
- Speech-to-text transcription with confidence scoring
- Behavioral signal extraction (pauses, fillers, speech rate)
- Sentence completeness detection for orchestration
- Audio analytics persistence

**Critical Design Principle:** Audio module is a **signal generator, not a decision-maker**. It produces transcripts, pause states, and behavioral metrics. The interview orchestration module decides what actions to take based on these signals.

**Architectural Isolation:** Audio module MUST NOT:

- Advance interview state directly
- Trigger scoring directly
- Modify `interview_exchanges` table
- Aggregate final evaluation results
- Make orchestration decisions

**Why Audio is Critical (Not a Toy Feature):**

- **Exchange Immutability:** Transcript finalization determines when exchange can be frozen
- **Evaluation Timing:** Completion detection triggers evaluation workflow
- **Runtime Orchestration:** Pause/completion signals control interview flow
- **Proctoring Signals:** Voice anomalies feed into integrity scoring

**Race Condition Risk:** If audio logic leaks casually into interview state machine, concurrent silence detection and new speech will create race conditions.

---

## 2. Owned Tables

### Primary Ownership

- `audio_analytics` - Per-exchange audio analysis results

```sql
CREATE TABLE audio_analytics (
    id SERIAL PRIMARY KEY,
    interview_exchange_id INTEGER UNIQUE REFERENCES interview_exchanges(id),
    transcript TEXT NOT NULL,
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    speech_rate_wpm FLOAT,
    filler_word_count INTEGER DEFAULT 0,
    sentiment_score FLOAT,
    pause_duration_ms INTEGER,
    speech_state VARCHAR(20) CHECK (speech_state IN ('complete', 'incomplete', 'continuing')),
    analysis_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Invariant:** One audio_analytics record per exchange_id (UNIQUE constraint enforced).

### Read-Only Access

- `interview_exchanges` - Bind audio session to exchange context (read exchange_id only)
- `interview_submissions` - Session context for ingestion
- `organizations` - Multi-tenancy scoping

### Forbidden Write Targets

- SHALL NOT write to `interview_exchanges` (immutability violation)
- SHALL NOT write to `evaluations` or `dimension_scores`
- SHALL NOT write to `interview_submissions`
- SHALL NOT write to proctoring tables directly (proctoring module owns those)

---

## 3. Input Constraints

### Audio Stream Ingestion

- **Format Requirements:**
  - Sample rate: 16kHz (preferred), 8kHz, 44.1kHz, 48kHz (acceptable)
  - Channels: Mono (preferred), Stereo (downmix to mono)
  - Encoding: PCM16, WAV, WebM, Opus (depending on source)
  - Chunk size: 100-500ms per chunk (streaming mode)

- **Session Context (Required):**
  - `interview_exchange_id` - Bind audio to specific exchange
  - `submission_id` - Interview session identifier
  - `organization_id` - Multi-tenancy scoping

- **Streaming Modes:**
  - **Real-time streaming:** Audio chunks arrive continuously
  - **Buffered mode:** Accumulate chunks before processing
  - **File upload:** Batch processing of recorded audio

### Transcription Input

- **Audio Duration:** 1s to 10 minutes per segment
- **Language:** Configurable (default: English)
- **Silence Threshold:** Configurable (default: 3000ms)
- **Max Recording Duration:** 5 minutes per response (configurable per template)

### Analysis Input

- **Transcript:** Non-empty text from transcription engine
- **Timestamp Data:** Segment-level timestamps (start, end, duration)
- **Audio Quality Metrics:** SNR, noise level (if available)

### Validation Rules

- `interview_exchange_id` MUST exist and be active
- Audio session MUST NOT be started for finalized exchanges
- Transcript MUST be UTF-8 encoded
- Confidence scores MUST be in range [0.0, 1.0]
- Speech rate MUST be positive (if calculated)

---

## 4. Output Guarantees

### AudioSignal Structure (Runtime Signal)

```python
@dataclass
class AudioSignal:
    # Core transcript
    transcript: str
    transcript_finalized: bool
    confidence_score: float  # 0.0 to 1.0

    # Completion detection
    speech_state: str  # 'complete' | 'incomplete' | 'continuing'
    pause_duration_ms: int
    sentence_complete: bool

    # Behavioral metrics
    filler_word_count: int
    filler_rate: float
    speech_rate_wpm: float

    # Sentiment/confidence
    sentiment_score: float  # -1.0 (negative) to 1.0 (positive)
    confidence_signal: float  # Derived from multiple factors

    # Technical metadata
    segments: List[TranscriptSegment]
    audio_quality_score: Optional[float]
    background_noise_detected: bool
    multiple_speakers_detected: bool
```

### TranscriptSegment Structure

```python
@dataclass
class TranscriptSegment:
    text: str
    start_time_ms: int
    end_time_ms: int
    confidence: float
    is_final: bool
```

### AudioAnalytics Structure (Persisted)

```python
@dataclass
class AudioAnalytics:
    id: int
    interview_exchange_id: int
    transcript: str
    confidence_score: float
    speech_rate_wpm: float
    filler_word_count: int
    sentiment_score: float
    pause_duration_ms: int
    speech_state: str
    analysis_metadata: dict  # Full AudioSignal data
    created_at: datetime
    updated_at: datetime
```

### Performance Guarantees

- **Transcription Latency:** <2s from speech end to transcript availability (real-time mode)
- **Analysis Latency:** <500ms to process transcript and generate signals
- **Total End-to-End:** Speech end → AudioSignal emission <3s p95
- **Silence Detection:** Trigger within 100ms of threshold crossing

### Consistency Guarantees

- One `audio_analytics` record per `interview_exchange_id` (UNIQUE constraint)
- Transcript MUST be stored before AudioSignal emitted to orchestrator
- Finalized transcripts MUST be immutable (no updates after `transcript_finalized=true`)

---

## 5. Invariants

### Transcript Finalization Invariant

```
IF transcript_finalized = true
THEN audio_analytics record MUST exist with matching transcript
AND no further modifications allowed to transcript
```

**Enforcement:** Check finalization flag before any transcript update, raise error if already finalized.

### Exchange Binding Invariant

```
EVERY audio session MUST be bound to exactly one interview_exchange_id
ONE exchange MAY have at most ONE audio_analytics record
```

**Enforcement:** UNIQUE constraint on `audio_analytics.interview_exchange_id`.

### Silence Detection Invariant

```
Silence detection MUST NOT trigger completion signal
Silence detection ONLY triggers completeness evaluation
Completeness evaluation determines speech_state
```

**Enforcement:** Separation of silence timer from completion logic.

### Signal Emission Invariant

```
AudioSignal emitted to orchestrator MUST be accompanied by:
- Persisted audio_analytics record
- Immutable transcript
- Valid speech_state
```

**Enforcement:** Atomic transaction: persist analytics → emit signal.

### Confidence Score Invariant

```
confidence_score = aggregate(
    transcription_confidence,
    audio_quality_score,
    completeness_confidence
)
Range: [0.0, 1.0]
```

**Enforcement:** Weighted average calculation with bounds checking.

---

## 6. Forbidden Behaviors

### State Mutation Violations

- SHALL NOT write to `interview_exchanges` table
- SHALL NOT modify exchange `stage` or `status` fields
- SHALL NOT update `interview_submissions` state
- SHALL NOT trigger evaluation workflow directly
- SHALL NOT advance interview orchestration state

### Decision-Making Violations

- SHALL NOT decide to proceed to next question
- SHALL NOT determine if answer is acceptable/unacceptable
- SHALL NOT compute final interview scores
- SHALL NOT apply rubric scoring logic
- SHALL NOT make pass/fail determinations

### Data Access Violations

- SHALL NOT read evaluation scores or rubric data
- SHALL NOT access other exchanges' audio data (cross-exchange)
- SHALL NOT expose audio analytics across tenant boundaries
- SHALL NOT cache transcripts globally (must be session-scoped)

### Timing Violations

- SHALL NOT assume silence always means completion
- SHALL NOT bypass completeness evaluation after silence
- SHALL NOT continue processing after exchange finalized
- SHALL NOT accept audio input for closed sessions

### Security Violations

- SHALL NOT store raw audio indefinitely (retention policy applies)
- SHALL NOT log full transcripts with PII in plaintext (use redaction)
- SHALL NOT expose transcription API keys in responses
- SHALL NOT allow replay attacks (session tokens must be validated)

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `audio/ingestion` - Audio stream capture and normalization
- `audio/transcription` - Speech-to-text conversion
- `audio/analysis` - Behavioral signal extraction
- `audio/persistence` - Repository for audio_analytics
- `shared/errors` - Exception types (AudioProcessingError, TranscriptionError)
- `shared/observability` - Logging and metrics
- `persistence/postgres` - Database session and models

### Dependents (Outbound)

- `interview/orchestration` - Consumes AudioSignal for flow control
- `evaluation/scoring` - Uses audio analytics for behavioral rubrics
- `proctoring/audio_anomaly` - Uses multi-speaker detection, voice stress signals
- `interview/session` - Validates exchange context before accepting audio

### External Systems

- **Web Speech API** - Browser-native STT (initial implementation)
- **Whisper API** - OpenAI transcription service (future)
- **Faster-Whisper** - Local CTranslate2 inference (future)
- **Vosk** - Lightweight offline STT (future)
- **spaCy** - NLP for sentence completeness (rule-based)
- **Browser WebRTC** - Real-time audio streaming

---

## 8. Event Contracts Emitted

### Audio Signal Events (Real-Time)

```json
{
  "event": "audio.signal.emitted",
  "exchange_id": 123,
  "submission_id": 45,
  "speech_state": "complete",
  "transcript_finalized": true,
  "confidence_score": 0.89,
  "pause_duration_ms": 3500,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

### Transcription Events

```json
{
  "event": "audio.transcription.partial",
  "exchange_id": 123,
  "partial_transcript": "I think the answer is...",
  "confidence": 0.85,
  "timestamp": "2026-02-13T10:29:55Z"
}
```

```json
{
  "event": "audio.transcription.finalized",
  "exchange_id": 123,
  "final_transcript": "I think the answer is dynamic programming.",
  "confidence": 0.92,
  "word_count": 7,
  "duration_ms": 4500,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

### Silence Detection Events

```json
{
  "event": "audio.silence.detected",
  "exchange_id": 123,
  "silence_duration_ms": 3200,
  "threshold_ms": 3000,
  "triggered_evaluation": true,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

### Behavioral Analysis Events

```json
{
  "event": "audio.analysis.completed",
  "exchange_id": 123,
  "filler_word_count": 4,
  "speech_rate_wpm": 145,
  "sentiment_score": 0.35,
  "confidence_signal": 0.78,
  "timestamp": "2026-02-13T10:30:01Z"
}
```

### Audio Anomaly Events (Proctoring)

```json
{
  "event": "audio.anomaly.detected",
  "exchange_id": 123,
  "submission_id": 45,
  "anomaly_type": "multiple_speakers",
  "confidence": 0.82,
  "timestamp": "2026-02-13T10:29:45Z"
}
```

---

## 9. Acceptance Criteria

### Transcription Accuracy

- [ ] Transcription engine produces text output for spoken input
- [ ] Confidence scores attached to each segment
- [ ] Partial transcripts available during streaming
- [ ] Final transcript marked with `is_final=true`
- [ ] Transcripts UTF-8 encoded and stored in `audio_analytics`

### Silence Detection

- [ ] Silence timer starts after last audio chunk received
- [ ] Timer resets if new audio chunk arrives before threshold
- [ ] Silence threshold configurable (default 3000ms)
- [ ] Silence detection triggers completeness evaluation (not direct completion)

### Sentence Completeness Evaluation

- [ ] Rule-based classifier detects sentence boundaries (. ? !)
- [ ] Detects incomplete conjunctions ("because", "and", "but" at end)
- [ ] Uses spaCy dependency parsing to check structural completeness
- [ ] Returns `speech_state: complete | incomplete | continuing`
- [ ] Confidence score attached to completeness determination

### Pause vs Completion Distinction

- [ ] Natural pause detected: silence < threshold OR sentence incomplete
- [ ] Completion detected: silence >= threshold AND sentence complete
- [ ] Continuing detected: new speech before threshold expires
- [ ] AudioSignal includes both `speech_state` and `pause_duration_ms`

### Filler Word Detection

- [ ] Rule-based list matches common fillers (um, uh, like, you know)
- [ ] Filler count included in AudioSignal
- [ ] Filler rate calculated (fillers / total words)

### Speech Rate Calculation

- [ ] Words per minute (WPM) calculated from transcript and duration
- [ ] Long pause frequency tracked (pauses > 1 second)
- [ ] Speech rate included in audio_analytics

### Sentiment Analysis

- [ ] Basic sentiment scoring using VADER or TextBlob
- [ ] Sentiment score range: -1.0 (negative) to 1.0 (positive)
- [ ] Sentiment included in confidence_signal calculation

### Persistence

- [ ] Audio analytics written to database before signal emission
- [ ] UNIQUE constraint on exchange_id enforced (one record per exchange)
- [ ] Transcript immutable after finalization
- [ ] Analysis metadata stored in JSONB field

### Integration with Orchestrator

- [ ] AudioSignal emitted to interview orchestrator
- [ ] Orchestrator decides next action based on speech_state
- [ ] Audio module does NOT advance interview state
- [ ] Race conditions handled: concurrent silence and new speech

### Multi-Tenancy

- [ ] Audio analytics scoped to organization_id
- [ ] No cross-tenant audio data access
- [ ] Transcription service calls include tenant context

---

## 10. Testing Guide

See [TESTING.md](TESTING.md) for comprehensive testing strategies.

**Key Testing Requirements:**

- Mock transcription engines for unit tests
- Simulate silence detection race conditions
- Validate sentence completeness classifier accuracy
- Test concurrent audio streams
- Verify exchange immutability after finalization

---

## 11. Edge Cases

### Transcription Edge Cases

- **Empty audio:** No speech detected → return empty transcript with warning
- **Background noise only:** Transcription confidence very low, may return gibberish
- **Overlapping speech:** Multiple speakers → separate detection, flag anomaly
- **Audio corruption:** Garbled input → transcription failure, return error signal
- **Very long silence:** >30s silence → timeout, finalize with incomplete state

### Silence Detection Edge Cases

- **Speech resumes just before threshold:** Cancel silence timer, reset threshold
- **Very short utterances:** "Yes", "No" → immediately complete (if sentence boundary detected)
- **False silence (audio glitch):** Brief dropout <500ms → do not trigger evaluation
- **Continuous speech >5 minutes:** Force finalization regardless of completeness

### Completeness Evaluation Edge Cases

- **Ends with "because…":** Incomplete (pending clause)
- **Ends with "and…":** Incomplete (conjunction)
- **Ends with "I think.":** Complete (sentence boundary + root verb)
- **Ends with "The answer is":** Incomplete (no complement)
- **Single word response:** "Yes." → Complete if followed by pause

### Filler Word Edge Cases

- **"Like" as verb:** "I like Python" → Not a filler (context-dependent)
- **"Um" at start:** Initial hesitation → count as filler
- **Multiple consecutive fillers:** "um, uh, like" → count each occurrence

### Concurrent Event Edge Cases

- **Silence timer fires + new speech arrives simultaneously:**
  - Priority: New speech cancels evaluation
  - Reset silence timer
  - Log race condition event

- **Finalization requested + new audio chunk:**
  - Reject new audio
  - Return error: exchange already finalized

- **Multiple parallel transcriptions (should not happen):**
  - Detect duplicate exchange_id
  - Reject second transcription attempt
  - Log error

### Browser API Edge Cases

- **Web Speech API unavailable:** Fallback to file upload mode
- **Microphone permission denied:** Clear error message, cannot proceed
- **Browser loses audio stream:** Attempt reconnection, finalize if timeout
- **Cross-browser differences:** Chrome vs Firefox vs Safari transcription quality

---

## 12. Concurrency Concerns

### Silence Timer Race Condition

**Scenario:** Silence timer expires while candidate resumes speaking.

**Mitigation:**

```python
# Atomic flag check before triggering evaluation
if silence_timer_expired and not new_audio_received:
    trigger_completeness_evaluation()
else:
    reset_silence_timer()
```

### Transcript Finalization Race

**Scenario:** Two concurrent requests to finalize transcript.

**Mitigation:**

- Use database-level UNIQUE constraint on `interview_exchange_id`
- Optimistic locking: check `transcript_finalized` flag before update
- First finalization wins, second returns error

### Streaming Chunk Ordering

**Scenario:** Audio chunks arrive out of order (network jitter).

**Mitigation:**

- Include sequence number in each chunk
- Buffer chunks and reorder before processing
- Detect gaps, request retransmission if necessary

### Multi-Speaker Detection Race

**Scenario:** Speaker detection runs while transcription is ongoing.

**Mitigation:**

- Run detection on buffered audio (not live stream)
- Update anomaly flags asynchronously (do not block transcription)
- Log anomaly events separately from transcript events

### Analytics Persistence vs Signal Emission

**Scenario:** Database write fails after AudioSignal emitted.

**Mitigation:**

- **Transaction order:** Persist analytics FIRST, then emit signal
- If persistence fails, do NOT emit signal
- If signal emission fails, retry async (idempotent)

### Session Cleanup Race

**Scenario:** Exchange finalized while audio processing in progress.

**Mitigation:**

- Check exchange status before accepting new audio
- Cancel in-flight processing if exchange closed
- Cleanup timers and buffers on session termination

---

## 13. Future Enhancements

### Advanced Transcription

- **Whisper Integration:** Higher accuracy, multilingual support
- **Faster-Whisper:** Real-time streaming with CTranslate2 optimization
- **Speaker Diarization:** Separate transcripts for multiple speakers
- **Accent Adaptation:** Fine-tuned models for regional accents

### Enhanced Analysis

- **ML-Based Completeness Classifier:** Replace rule-based with fine-tuned BERT
- **Voice Stress Detection:** Analyze pitch, tempo changes for confidence
- **Emotion Recognition (Audio Features Only):** Arousal, valence from prosody
- **Cognitive Load Estimation:** Pause patterns, speech disfluency analysis

### Proctoring Signals

- **Multi-Speaker Detection:** Identify coaching/assistance
- **Voice Biometric Matching:** Verify candidate identity (with consent)
- **Background Audio Classification:** Detect prohibited device sounds

### Performance Optimization

- **Edge Inference:** Run lightweight STT models in browser (WASM)
- **Adaptive Buffering:** Adjust chunk size based on network conditions
- **Caching:** Cache common filler word patterns, sentence structures

### User Experience

- **Live Transcript Display:** Show candidate their speech in real-time
- **Pronunciation Feedback:** Highlight unclear segments
- **Retry Mechanism:** Allow candidate to re-record if transcription fails

---

**End of Audio Module Requirements**
