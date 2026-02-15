# Audio Ingestion Module

## 1. Purpose

**Why this submodule exists:**

The Audio Ingestion module is the **entry point** for all audio data in voice-based interviews. It:

- Accepts real-time audio streams from WebRTC clients
- Normalizes audio format (sample rate, channels, encoding)
- Detects silence periods using configurable thresholds
- Binds audio sessions to `interview_exchange_id`
- Buffers audio chunks for downstream transcription
- Manages audio session lifecycle (start, pause, resume, stop)

**Critical responsibility:** Silence detection must be **race-safe**. If a silence timer expires while new audio arrives, the timer must be **atomically cancelled** to prevent spurious evaluation triggers.

---

## 2. Owned Tables / Entities

**None.** This module is stateless. All audio metadata is persisted by the `audio.persistence` module to `audio_analytics` after transcription.

---

## 3. Input Contracts

### AudioStreamRequest

```python
@dataclass
class AudioStreamRequest:
    interview_exchange_id: int        # REQUIRED: Bind to exchange
    audio_chunk: bytes                # REQUIRED: Raw audio data
    sample_rate: int                  # REQUIRED: Audio sample rate (Hz)
    channels: int = 1                 # Default: mono
    timestamp_ms: Optional[int] = None  # Client-side timestamp (for sync)
    chunk_sequence: Optional[int] = None  # For ordering verification
```

### AudioSessionControl

```python
@dataclass
class AudioSessionControl:
    interview_exchange_id: int
    action: Literal["start", "pause", "resume", "stop"]
    reason: Optional[str] = None  # e.g., "user paused", "network interruption"
```

---

## 4. Output Contracts

### AudioChunk (Internal)

```python
@dataclass
class AudioChunk:
    exchange_id: int
    audio_data: bytes
    sample_rate: int
    channels: int
    timestamp_ms: int
    duration_ms: int
    normalized: bool  # True if resampled/converted
```

### SilenceDetectedEvent

```python
@dataclass
class SilenceDetectedEvent:
    exchange_id: int
    silence_duration_ms: int  # How long silence lasted
    last_audio_timestamp_ms: int
    should_evaluate: bool  # True if ≥ threshold, completeness classifier should run
    reason: Literal["threshold_reached", "session_ended"]
```

---

## 5. Acceptance Criteria

### Functional Requirements

1. **Audio Format Normalization:**
   - Accept audio at various sample rates (8kHz, 16kHz, 48kHz)
   - Resample all audio to **16kHz mono** for transcription (standard for speech-to-text)
   - Support common encodings: PCM, Opus, μ-law

2. **Silence Detection:**
   - Configurable silence threshold (default: **3000ms**)
   - Emit `SilenceDetectedEvent` when threshold reached
   - Timer resets on any new audio chunk
   - Must handle race condition: silence expires + new audio arrives simultaneously

3. **Session Management:**
   - Bind audio stream to `interview_exchange_id`
   - Validate exchange exists and is in `responding` stage
   - Support pause/resume (e.g., candidate asks to think)
   - Cleanly close session on `stop` action

4. **Buffering:**
   - Buffer audio chunks for transcription (500ms windows)
   - Forward buffered chunks to `audio.transcription` module
   - Drop buffers on session close

### Non-Functional Requirements

1. **Latency:** <100ms from audio chunk receipt to forwarding to transcription
2. **Thread-Safety:** Multiple concurrent audio sessions per tenant
3. **No Cross-Session Interference:** Exchange 1's audio must not affect Exchange 2's silence timer
4. **Graceful Degradation:** If transcription service is unavailable, buffer audio (up to 30s max) and retry

---

## 6. Invariants & Constraints

### Must Hold

1. **One Active Session Per Exchange:** Cannot have two concurrent audio streams for the same `interview_exchange_id`
2. **Silence Timer Atomicity:** Silence timer expiration must atomically check if new audio arrived since timer start
3. **Exchange Must Be in `responding` Stage:** Cannot accept audio if exchange is in `evaluating`, `proctoring`, or `completed` stages
4. **Sample Rate Normalization:** All audio forwarded to transcription must be **16kHz mono**

### Forbidden

- MUST NOT write to `interview_exchanges` table
- MUST NOT trigger state transitions (only emit `SilenceDetectedEvent`)
- MUST NOT persist audio chunks to disk (GDPR: audio is ephemeral, only transcripts persist)
- MUST NOT accept audio for finalized exchanges

---

## 7. Concurrency & Race Conditions

### Critical Race: Silence Timer vs New Audio

**Scenario:**

1. Last audio chunk at `t=1000ms`
2. Silence timer starts (threshold=3000ms, expires at `t=4000ms`)
3. At `t=3999ms`, new audio chunk arrives
4. At `t=4000ms`, silence timer callback fires

**Solution:**

```python
class SilenceDetector:
    def __init__(self, threshold_ms: int):
        self.threshold_ms = threshold_ms
        self.last_audio_timestamp = None
        self.timer = None
        self.lock = threading.Lock()

    def on_audio_chunk(self, chunk: AudioChunk):
        with self.lock:
            # Cancel existing timer
            if self.timer:
                self.timer.cancel()

            # Update timestamp
            self.last_audio_timestamp = chunk.timestamp_ms

            # Start new timer
            self.timer = threading.Timer(
                self.threshold_ms / 1000.0,
                self._check_silence
            )
            self.timer.start()

    def _check_silence(self):
        with self.lock:
            # Atomic check: did new audio arrive since timer started?
            time_since_last_audio = current_time() - self.last_audio_timestamp

            if time_since_last_audio >= self.threshold_ms:
                # True silence, emit event
                self._emit_silence_event()
            else:
                # New audio arrived, false alarm
                pass
```

### Concurrent Sessions

Multiple interviews can run simultaneously. Use **session isolation**:

```python
# Global session registry (thread-safe)
_active_sessions: Dict[int, AudioSession] = {}
_sessions_lock = threading.Lock()

def get_or_create_session(exchange_id: int) -> AudioSession:
    with _sessions_lock:
        if exchange_id not in _active_sessions:
            _active_sessions[exchange_id] = AudioSession(exchange_id)
        return _active_sessions[exchange_id]
```

---

## 8. Integration Points

### Upstream (Callers)

1. **API Layer (`app.api.audio`):**
   - Endpoint: `POST /interviews/{id}/exchanges/{eid}/audio/stream`
   - Sends `AudioStreamRequest` chunks via WebSocket
   - Receives `SilenceDetectedEvent` notifications

### Downstream (Dependencies)

1. **Transcription Module (`app.audio.transcription`):**
   - Receives normalized `AudioChunk` buffers
   - Returns partial/final transcripts

2. **Interview Orchestrator (`app.interview.orchestration`):**
   - Receives `SilenceDetectedEvent`
   - Decides whether to trigger completeness evaluation or wait for more audio

3. **Validation Module (`app.admin.validation`):**
   - Validates `interview_exchange_id` exists and is in `responding` stage

---

## 9. Edge Cases to Handle

1. **Audio Arrives After Session Closed:**
   - Reject with `SessionClosedError`

2. **Extremely Short Audio (<100ms):**
   - Still forward to transcription (might be single word like "Yes")

3. **Network Jitter (Chunks Out of Order):**
   - Use `chunk_sequence` to reorder
   - If gap >500ms, emit warning but continue

4. **Client Disconnects Without `stop` Action:**
   - Auto-close session after 10s timeout
   - Emit `SilenceDetectedEvent` with `reason="session_ended"`

5. **Candidate Pauses Mid-Sentence:**
   - If silence threshold reached, emit `SilenceDetectedEvent`
   - Completeness classifier (in `analysis` module) will determine if sentence was incomplete
   - Orchestrator may wait for more audio or prompt candidate

6. **Extremely Long Silence (>30s):**
   - Emit `SilenceDetectedEvent` even if session still active
   - Orchestrator may interpret as candidate abandoning question

---

## 10. Example Usage

### Starting Audio Session

```python
from app.audio.ingestion import AudioIngestionService

service = AudioIngestionService()

# Start session
service.start_session(
    exchange_id=123,
    sample_rate=16000
)

# Stream audio chunks
for chunk in audio_stream:
    service.ingest_chunk(AudioStreamRequest(
        interview_exchange_id=123,
        audio_chunk=chunk,
        sample_rate=48000,  # Will be resampled to 16kHz
        timestamp_ms=get_timestamp()
    ))

# Silence detected after 3s
# -> SilenceDetectedEvent emitted to orchestrator
```

### Handling Silence Event

```python
def on_silence_detected(event: SilenceDetectedEvent):
    if event.should_evaluate:
        # Trigger completeness evaluation
        orchestrator.evaluate_response_completeness(event.exchange_id)
    else:
        # Wait for more audio
        pass
```

---

## 11. Configuration

### Environment Variables

```bash
# Silence detection threshold (milliseconds)
AUDIO_SILENCE_THRESHOLD_MS=3000

# Audio buffer size (milliseconds)
AUDIO_BUFFER_WINDOW_MS=500

# Maximum buffered audio duration (seconds)
AUDIO_MAX_BUFFER_DURATION_S=30

# Session timeout (seconds, for detecting disconnected clients)
AUDIO_SESSION_TIMEOUT_S=10

# Target sample rate for transcription (Hz)
AUDIO_TARGET_SAMPLE_RATE=16000
```

---

## 12. Future Enhancements

1. **Adaptive Silence Threshold:**
   - If candidate consistently pauses for <2s between sentences, lower threshold to 2s
   - If candidate pauses mid-sentence frequently, raise threshold to 5s

2. **Audio Quality Checks:**
   - Detect background noise, microphone issues
   - Warn candidate if audio quality is poor

3. **Client-Side Voice Activity Detection (VAD):**
   - Client pre-filters silence before sending chunks
   - Reduces bandwidth usage

4. **Multi-Language Support:**
   - Different silence thresholds for different languages (some languages have longer natural pauses)

5. **Audio Compression:**
   - Accept Opus-encoded audio to reduce bandwidth
   - Decode server-side before transcription

---

**End of Audio Ingestion Module Requirements**
