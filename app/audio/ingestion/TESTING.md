# Audio Ingestion Module Testing Guide

## Testing Philosophy

Ingestion testing focuses on **race conditions** and **session isolation**. The most critical test is: **silence timer expires while new audio arrives**.

Tests use:

- **Mocked audio chunks** (no real microphones)
- **Time manipulation** (`time.sleep`, `freezegun` for deterministic timing)
- **Concurrent audio streams** (ensure no cross-session interference)

---

## Test Structure

```
tests/
├── unit/
│   └── audio/
│       └── ingestion/
│           ├── test_audio_normalizer.py
│           ├── test_silence_detector.py
│           ├── test_session_manager.py
│           └── test_buffer_manager.py
└── integration/
    └── audio/
        └── ingestion/
            ├── test_audio_ingestion_service.py
            └── test_concurrent_sessions.py
```

---

## 1. Unit Tests

### Audio Normalization Tests

```python
# tests/unit/audio/ingestion/test_audio_normalizer.py

import pytest
import numpy as np
from app.audio.ingestion.normalizer import AudioNormalizer

def test_resample_48khz_to_16khz():
    \"\"\"Resample 48kHz audio to 16kHz\"\"\"
    normalizer = AudioNormalizer(target_sample_rate=16000)

    # Generate 1 second of 48kHz audio
    duration_s = 1.0
    sample_rate_in = 48000
    audio_in = np.random.randn(int(duration_s * sample_rate_in))

    audio_out = normalizer.resample(audio_in, sample_rate_in)

    # Output should be 16k samples
    assert len(audio_out) == 16000
    assert normalizer.output_sample_rate == 16000

def test_convert_stereo_to_mono():
    \"\"\"Convert stereo audio to mono\"\"\"
    normalizer = AudioNormalizer(target_channels=1)

    # Stereo audio (2 channels)
    stereo_audio = np.random.randn(16000, 2)  # 1s of 16kHz stereo

    mono_audio = normalizer.to_mono(stereo_audio)

    assert mono_audio.shape == (16000,)  # 1D array

def test_normalize_volume():
    \"\"\"Normalize audio volume to prevent clipping\"\"\"
    normalizer = AudioNormalizer()

    # Audio with excessive volume
    loud_audio = np.random.randn(16000) * 10.0  # 10x normal

    normalized = normalizer.normalize_volume(loud_audio)

    # Peak should be < 1.0
    assert np.max(np.abs(normalized)) <= 1.0

def test_detect_silence_in_chunk():
    \"\"\"Detect if audio chunk is mostly silence\"\"\"
    normalizer = AudioNormalizer()

    # Pure silence
    silence = np.zeros(16000)
    assert normalizer.is_silence(silence) is True

    # Audio with speech
    speech = np.random.randn(16000) * 0.5
    assert normalizer.is_silence(speech) is False

    # Very quiet audio (below threshold)
    quiet = np.random.randn(16000) * 0.01
    assert normalizer.is_silence(quiet) is True

def test_opus_decoding():
    \"\"\"Decode Opus-encoded audio\"\"\"
    normalizer = AudioNormalizer()

    # Mock Opus-encoded data
    opus_data = b"\\x01\\x02\\x03..."  # Placeholder

    # Decode (requires pyogg or similar)
    pcm_data = normalizer.decode_opus(opus_data)

    assert isinstance(pcm_data, np.ndarray)
    assert len(pcm_data) > 0
```

### Silence Detection Tests

```python
# tests/unit/audio/ingestion/test_silence_detector.py

import pytest
import time
from unittest.mock import Mock
from app.audio.ingestion.silence_detector import SilenceDetector

def test_silence_timer_starts_after_audio():
    \"\"\"Timer starts after first audio chunk\"\"\"
    detector = SilenceDetector(threshold_ms=3000)

    detector.on_audio_chunk(timestamp_ms=1000)

    assert detector.timer is not None
    assert detector.timer.is_alive()

def test_silence_timer_resets_on_new_audio():
    \"\"\"Timer resets when new audio arrives\"\"\"
    detector = SilenceDetector(threshold_ms=3000)

    detector.on_audio_chunk(timestamp_ms=1000)
    first_timer = detector.timer

    time.sleep(1)

    detector.on_audio_chunk(timestamp_ms=2000)
    second_timer = detector.timer

    # Timer should be different object (old one cancelled)
    assert first_timer is not second_timer
    assert not first_timer.is_alive()
    assert second_timer.is_alive()

def test_silence_event_emitted_after_threshold():
    \"\"\"SilenceDetectedEvent emitted after threshold\"\"\"
    detector = SilenceDetector(threshold_ms=1000)  # 1s for test speed

    events = []
    detector.on_silence_detected(lambda e: events.append(e))

    detector.on_audio_chunk(timestamp_ms=1000)

    # Wait for threshold
    time.sleep(1.2)

    assert len(events) == 1
    assert events[0].silence_duration_ms >= 1000

def test_race_condition_new_audio_cancels_timer():
    \"\"\"New audio arriving just before timer expires cancels evaluation\"\"\"
    detector = SilenceDetector(threshold_ms=1000)

    events = []
    detector.on_silence_detected(lambda e: events.append(e))

    detector.on_audio_chunk(timestamp_ms=1000)

    # Wait almost to threshold
    time.sleep(0.9)

    # New audio arrives just before timer expires
    detector.on_audio_chunk(timestamp_ms=1900)

    # Wait a bit more
    time.sleep(0.2)

    # No event should have been emitted (timer was cancelled)
    assert len(events) == 0

def test_silence_detector_thread_safety():
    \"\"\"Silence detector is thread-safe\"\"\"
    import threading

    detector = SilenceDetector(threshold_ms=1000)

    events = []
    detector.on_silence_detected(lambda e: events.append(e))

    # Simulate concurrent audio chunks
    def send_chunk(timestamp):
        detector.on_audio_chunk(timestamp_ms=timestamp)

    threads = [
        threading.Thread(target=send_chunk, args=(i * 100,))
        for i in range(10)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should not crash, timer should be from last chunk
    time.sleep(1.2)
    assert len(events) == 1  # Only one silence event

def test_configurable_silence_threshold():
    \"\"\"Silence threshold is configurable\"\"\"
    detector_3s = SilenceDetector(threshold_ms=3000)
    detector_5s = SilenceDetector(threshold_ms=5000)

    assert detector_3s.threshold_ms == 3000
    assert detector_5s.threshold_ms == 5000

def test_silence_reason_threshold_vs_session_ended():
    \"\"\"Distinguish between threshold reached and session ended\"\"\"
    detector = SilenceDetector(threshold_ms=1000)

    events = []
    detector.on_silence_detected(lambda e: events.append(e))

    detector.on_audio_chunk(timestamp_ms=1000)
    time.sleep(1.2)

    # Threshold reached
    assert events[0].reason == "threshold_reached"

    # Now close session explicitly
    events.clear()
    detector.close_session()

    # Should emit event with different reason
    assert len(events) == 1
    assert events[0].reason == "session_ended"
```

### Session Manager Tests

```python
# tests/unit/audio/ingestion/test_session_manager.py

import pytest
from app.audio.ingestion.session_manager import AudioSessionManager
from app.audio.ingestion.exceptions import SessionAlreadyActiveError, SessionNotFoundError

def test_start_new_session():
    \"\"\"Start new audio session\"\"\"
    manager = AudioSessionManager()

    session = manager.start_session(exchange_id=123, sample_rate=16000)

    assert session.exchange_id == 123
    assert session.is_active is True

def test_cannot_start_duplicate_session():
    \"\"\"Cannot start two sessions for same exchange\"\"\"
    manager = AudioSessionManager()

    manager.start_session(exchange_id=123, sample_rate=16000)

    with pytest.raises(SessionAlreadyActiveError):
        manager.start_session(exchange_id=123, sample_rate=16000)

def test_pause_and_resume_session():
    \"\"\"Pause and resume audio session\"\"\"
    manager = AudioSessionManager()

    session = manager.start_session(exchange_id=123, sample_rate=16000)

    manager.pause_session(exchange_id=123, reason="user paused")
    assert session.is_paused is True

    manager.resume_session(exchange_id=123)
    assert session.is_paused is False

def test_stop_session():
    \"\"\"Stop audio session\"\"\"
    manager = AudioSessionManager()

    manager.start_session(exchange_id=123, sample_rate=16000)

    manager.stop_session(exchange_id=123)

    # Session should be removed
    with pytest.raises(SessionNotFoundError):
        manager.get_session(exchange_id=123)

def test_session_timeout():
    \"\"\"Session auto-closes after timeout\"\"\"
    manager = AudioSessionManager(timeout_s=2)

    manager.start_session(exchange_id=123, sample_rate=16000)

    # Wait for timeout
    time.sleep(2.5)

    # Session should be closed
    with pytest.raises(SessionNotFoundError):
        manager.get_session(exchange_id=123)

def test_concurrent_sessions_isolated():
    \"\"\"Multiple concurrent sessions are isolated\"\"\"
    manager = AudioSessionManager()

    session_1 = manager.start_session(exchange_id=123, sample_rate=16000)
    session_2 = manager.start_session(exchange_id=456, sample_rate=16000)

    assert session_1.exchange_id != session_2.exchange_id

    # Pause session 1
    manager.pause_session(exchange_id=123)

    # Session 2 should still be active
    assert session_2.is_paused is False
```

### Buffer Manager Tests

```python
# tests/unit/audio/ingestion/test_buffer_manager.py

import pytest
from app.audio.ingestion.buffer_manager import AudioBufferManager

def test_buffer_chunks_by_time_window():
    \"\"\"Buffer audio chunks into time windows\"\"\"
    manager = AudioBufferManager(window_ms=500)

    # Add chunks over 1 second
    for i in range(10):
        manager.add_chunk(
            audio_data=np.random.randn(1600),  # 100ms at 16kHz
            timestamp_ms=i * 100
        )

    # Should have 2 windows (500ms each)
    windows = manager.get_windows()
    assert len(windows) == 2

def test_buffer_flush_on_silence():
    \"\"\"Flush buffer when silence detected\"\"\"
    manager = AudioBufferManager(window_ms=500)

    manager.add_chunk(audio_data=np.random.randn(8000), timestamp_ms=0)

    # Flush
    flushed = manager.flush()

    assert len(flushed) > 0
    assert manager.is_empty()

def test_buffer_max_duration():
    \"\"\"Buffer has max duration limit\"\"\"
    manager = AudioBufferManager(window_ms=500, max_duration_s=2)

    # Add 3 seconds of audio
    for i in range(30):
        manager.add_chunk(
            audio_data=np.random.randn(1600),
            timestamp_ms=i * 100
        )

    # Should only keep last 2 seconds
    windows = manager.get_windows()
    total_duration_ms = sum(w.duration_ms for w in windows)
    assert total_duration_ms <= 2000

def test_buffer_ordering():
    \"\"\"Chunks ordered by timestamp even if out of order\"\"\"
    manager = AudioBufferManager(window_ms=500)

    # Add chunks out of order
    manager.add_chunk(audio_data=b"chunk3", timestamp_ms=300)
    manager.add_chunk(audio_data=b"chunk1", timestamp_ms=100)
    manager.add_chunk(audio_data=b"chunk2", timestamp_ms=200)

    windows = manager.get_windows()
    chunks = windows[0].chunks

    # Should be ordered
    assert chunks[0].timestamp_ms < chunks[1].timestamp_ms < chunks[2].timestamp_ms
```

---

## 2. Integration Tests

### Audio Ingestion Service Tests

```python
# tests/integration/audio/ingestion/test_audio_ingestion_service.py

import pytest
from app.audio.ingestion import AudioIngestionService

@pytest.fixture
def db_with_exchange(db_session):
    \"\"\"Create test exchange\"\"\"
    from app.persistence.models import InterviewExchange

    exchange = InterviewExchange(
        submission_id=1,
        question_snapshot={"text": "Test question"},
        stage="responding"
    )
    db_session.add(exchange)
    db_session.commit()
    return db_session, exchange.id

def test_ingest_audio_chunk_workflow(db_with_exchange):
    \"\"\"Full workflow: start session, ingest chunks, detect silence\"\"\"
    db_session, exchange_id = db_with_exchange

    service = AudioIngestionService(db_session)

    # Start session
    service.start_session(exchange_id=exchange_id, sample_rate=16000)

    # Ingest chunks
    for i in range(5):
        service.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=exchange_id,
            audio_chunk=np.random.randn(1600).tobytes(),
            sample_rate=16000,
            timestamp_ms=i * 100
        ))

    # Wait for silence
    time.sleep(3.5)

    # Should have emitted silence event
    # (verify via event handler in real implementation)

def test_cannot_ingest_for_non_responding_exchange(db_session):
    \"\"\"Cannot ingest audio if exchange not in responding stage\"\"\"
    from app.persistence.models import InterviewExchange

    exchange = InterviewExchange(
        submission_id=1,
        question_snapshot={"text": "Test"},
        stage="evaluating"  # Not responding
    )
    db_session.add(exchange)
    db_session.commit()

    service = AudioIngestionService(db_session)

    with pytest.raises(InvalidExchangeStageError):
        service.start_session(exchange_id=exchange.id, sample_rate=16000)

def test_session_cleanup_on_finalization(db_with_exchange):
    \"\"\"Session cleaned up when exchange finalized\"\"\"
    db_session, exchange_id = db_with_exchange

    service = AudioIngestionService(db_session)

    service.start_session(exchange_id=exchange_id, sample_rate=16000)

    # Finalize exchange
    service.finalize_session(exchange_id=exchange_id)

    # Cannot ingest more audio
    with pytest.raises(SessionClosedError):
        service.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=exchange_id,
            audio_chunk=b"data",
            sample_rate=16000
        ))
```

### Concurrent Sessions Tests

```python
# tests/integration/audio/ingestion/test_concurrent_sessions.py

def test_concurrent_sessions_no_interference():
    \"\"\"Multiple concurrent sessions don't interfere\"\"\"
    import threading

    service = AudioIngestionService()

    # Start two sessions
    service.start_session(exchange_id=123, sample_rate=16000)
    service.start_session(exchange_id=456, sample_rate=16000)

    results = {"123": [], "456": []}

    def ingest_for_session(exchange_id):
        for i in range(10):
            service.ingest_chunk(AudioStreamRequest(
                interview_exchange_id=exchange_id,
                audio_chunk=np.random.randn(1600).tobytes(),
                sample_rate=16000,
                timestamp_ms=i * 100
            ))
            results[str(exchange_id)].append(i)

    # Run concurrently
    t1 = threading.Thread(target=ingest_for_session, args=(123,))
    t2 = threading.Thread(target=ingest_for_session, args=(456,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both should have completed without errors
    assert len(results["123"]) == 10
    assert len(results["456"]) == 10

def test_silence_detector_per_session():
    \"\"\"Each session has independent silence detector\"\"\"
    service = AudioIngestionService()

    service.start_session(exchange_id=123, sample_rate=16000)
    service.start_session(exchange_id=456, sample_rate=16000)

    # Ingest audio for session 123
    service.ingest_chunk(AudioStreamRequest(
        interview_exchange_id=123,
        audio_chunk=b"data",
        sample_rate=16000,
        timestamp_ms=1000
    ))

    # Wait for session 123 silence (3s)
    time.sleep(3.5)

    # Session 123 should detect silence
    # Session 456 should NOT detect silence (no audio sent)
```

---

## Test Coverage Requirements

- **Unit Tests:** >95% code coverage (ingestion is critical)
- **Integration Tests:** All database interactions + concurrent sessions
- **Race Condition Tests:** Must pass 100% (silence timer + new audio)

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/audio/ingestion/ -v

# Integration tests
pytest tests/integration/audio/ingestion/ -v

# Race condition tests specifically
pytest tests/unit/audio/ingestion/test_silence_detector.py::test_race_condition_new_audio_cancels_timer -v

# Coverage
pytest tests/audio/ingestion/ --cov=app/audio/ingestion --cov-report=html
```

---

## Critical Tests (Must Pass)

- [ ] Silence timer atomically checks for new audio before emitting event
- [ ] Concurrent sessions are isolated (no cross-session timer interference)
- [ ] Audio normalized to 16kHz mono before forwarding to transcription
- [ ] Cannot start duplicate session for same exchange
- [ ] Session auto-closes after timeout (10s default)
- [ ] Cannot ingest audio for finalized exchange

---

**End of Audio Ingestion Module Testing Guide**
