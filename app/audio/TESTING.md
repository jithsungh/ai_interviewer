# Audio Module Testing Guide

## Testing Philosophy

Audio module testing is critical because race conditions in silence detection and transcript finalization can corrupt interview state. Tests must cover:

1. **Race condition scenarios** (silence timer vs new speech)
2. **Completeness classifier accuracy** (incomplete vs complete sentences)
3. **Concurrent audio streams** (no cross-session interference)
4. **Exchange immutability** (no writes after finalization)
5. **Integration timing** (signal emission order)

Most tests use **mocked transcription engines** to avoid external API dependencies and ensure deterministic results.

---

## Test Structure

```
tests/
├── unit/
│   └── audio/
│       ├── test_silence_detection.py
│       ├── test_completeness_classifier.py
│       ├── test_filler_detection.py
│       ├── test_speech_rate.py
│       └── test_signal_generation.py
├── integration/
│   └── audio/
│       ├── test_audio_analytics_repository.py
│       ├── test_transcription_pipeline.py
│       ├── test_orchestrator_integration.py
│       └── test_exchange_binding.py
└── e2e/
    └── audio/
        ├── test_voice_interview_flow.py
        └── test_race_conditions.py
```

---

## 1. Unit Tests (Mocked Transcription)

### Silence Detection Tests

```python
# tests/unit/audio/test_silence_detection.py

import pytest
import time
from unittest.mock import Mock, patch
from app.audio.ingestion.silence_detector import SilenceDetector

def test_silence_timer_starts_after_last_audio():
    """Silence timer starts only after audio chunk ends"""
    detector = SilenceDetector(threshold_ms=3000)

    detector.on_audio_chunk(b"audio_data_1", timestamp=1000)
    assert detector.is_silent() is False

    # No new audio for 2 seconds (below threshold)
    time.sleep(2)
    assert detector.is_silent() is False

    # No new audio for 1 more second (crosses threshold)
    time.sleep(1)
    assert detector.is_silent() is True

def test_silence_timer_resets_on_new_audio():
    """New audio resets silence timer"""
    detector = SilenceDetector(threshold_ms=3000)

    detector.on_audio_chunk(b"audio_1", timestamp=1000)
    time.sleep(2.5)  # Almost at threshold

    # New audio arrives just before threshold
    detector.on_audio_chunk(b"audio_2", timestamp=3500)

    # Timer should reset, not silent yet
    assert detector.is_silent() is False

def test_silence_detection_triggers_evaluation_not_completion():
    """Silence detection triggers evaluation, not immediate completion"""
    detector = SilenceDetector(threshold_ms=3000)
    mock_callback = Mock()

    detector.on_silence_detected(mock_callback)

    detector.on_audio_chunk(b"audio", timestamp=1000)
    time.sleep(3.1)

    # Callback should be triggered
    mock_callback.assert_called_once()
    # But callback should NOT directly change interview state
    # (that's orchestrator's job)

def test_concurrent_silence_and_new_speech():
    \"\"\"Handle race: silence timer expires while new speech arrives\"\"\"
    detector = SilenceDetector(threshold_ms=3000)

    detector.on_audio_chunk(b"audio_1", timestamp=1000)

    # Simulate race: timer expires and new audio arrives simultaneously
    with patch('threading.Timer') as mock_timer:
        timer_callback = None

        def capture_callback(delay, callback):
            nonlocal timer_callback
            timer_callback = callback
            return Mock()

        mock_timer.side_effect = capture_callback

        detector.start_silence_timer()

        # New audio arrives
        detector.on_audio_chunk(b"audio_2", timestamp=4000)

        # Try to fire timer callback
        if timer_callback:
            timer_callback()

        # Should NOT trigger evaluation because audio arrived
        assert detector.evaluation_triggered is False
```

### Completeness Classifier Tests

```python
# tests/unit/audio/test_completeness_classifier.py

import pytest
from app.audio.analysis.completeness_classifier import CompletenessClassifier

def test_complete_sentence_with_period():
    \"\"\"Sentence ending with period is complete\"\"\"
    classifier = CompletenessClassifier()

    result = classifier.evaluate("I think the answer is dynamic programming.")

    assert result.speech_state == "complete"
    assert result.sentence_complete is True
    assert result.confidence > 0.8

def test_incomplete_sentence_with_conjunction():
    \"\"\"Sentence ending with conjunction is incomplete\"\"\"
    classifier = CompletenessClassifier()

    result = classifier.evaluate("The answer is correct because")

    assert result.speech_state == "incomplete"
    assert result.sentence_complete is False
    assert result.incomplete_reason == "ends_with_conjunction"

def test_incomplete_sentence_no_complement():
    \"\"\"Sentence missing complement is incomplete\"\"\"
    classifier = CompletenessClassifier()

    result = classifier.evaluate("I think the answer is")

    assert result.speech_state == "incomplete"
    assert result.sentence_complete is False
    assert result.incomplete_reason == "missing_complement"

def test_complete_one_word_response():
    \"\"\"Single word with punctuation can be complete\"\"\"
    classifier = CompletenessClassifier()

    result = classifier.evaluate("Yes.")

    assert result.speech_state == "complete"
    assert result.sentence_complete is True

def test_ambiguous_sentence_includes_confidence():
    \"\"\"Ambiguous cases have lower confidence\"\"\"
    classifier = CompletenessClassifier()

    result = classifier.evaluate("The algorithm works well")  # No period

    # May be incomplete (no punctuation) but structurally complete
    assert 0.5 < result.confidence < 0.8

def test_spacy_dependency_parsing():
    \"\"\"Uses spaCy to check structural completeness\"\"\"
    classifier = CompletenessClassifier()

    complete = "I solved the problem using recursion."
    incomplete = "When I looked at the problem"

    result_complete = classifier.evaluate(complete)
    result_incomplete = classifier.evaluate(incomplete)

    assert result_complete.speech_state == "complete"
    assert result_incomplete.speech_state == "incomplete"
```

### Filler Word Detection Tests

```python
# tests/unit/audio/test_filler_detection.py

from app.audio.analysis.filler_detector import FillerDetector

def test_common_fillers_detected():
    \"\"\"Common filler words detected\"\"\"
    detector = FillerDetector()

    transcript = "Um, I think, uh, the answer is, like, dynamic programming."

    result = detector.detect(transcript)

    assert result.filler_word_count == 4  # um, uh, like, and "I think" if configured
    assert "um" in result.filler_positions
    assert "uh" in result.filler_positions
    assert "like" in result.filler_positions

def test_like_as_verb_not_filler():
    \"\"\"'Like' used as verb not counted as filler\"\"\"
    detector = FillerDetector(context_aware=True)

    transcript = "I like Python programming."

    result = detector.detect(transcript)

    assert result.filler_word_count == 0

def test_filler_rate_calculation():
    \"\"\"Filler rate calculated correctly\"\"\"
    detector = FillerDetector()

    transcript = "Um so uh basically the answer is bubble sort"  # 2 fillers, 8 words

    result = detector.detect(transcript)

    assert result.filler_rate == pytest.approx(0.25, rel=0.01)  # 2/8

def test_multiple_consecutive_fillers():
    \"\"\"Consecutive fillers counted separately\"\"\"
    detector = FillerDetector()

    transcript = "Um uh like you know the answer"

    result = detector.detect(transcript)

    assert result.filler_word_count >= 3
```

### Speech Rate Tests

```python
# tests/unit/audio/test_speech_rate.py

from app.audio.analysis.speech_rate_analyzer import SpeechRateAnalyzer

def test_words_per_minute_calculation():
    \"\"\"WPM calculated from word count and duration\"\"\"
    analyzer = SpeechRateAnalyzer()

    transcript = "The quick brown fox jumps over the lazy dog"  # 9 words
    duration_ms = 3000  # 3 seconds

    result = analyzer.analyze(transcript, duration_ms)

    # 9 words in 3 seconds = 180 WPM
    assert result.speech_rate_wpm == pytest.approx(180, rel=0.1)

def test_long_pause_detection():
    \"\"\"Long pauses detected from segment timestamps\"\"\"
    analyzer = SpeechRateAnalyzer()

    segments = [
        {"text": "First part", "start": 0, "end": 2000},
        # 3 second gap
        {"text": "Second part", "start": 5000, "end": 7000}
    ]

    result = analyzer.analyze_segments(segments)

    assert result.long_pause_count == 1
    assert result.longest_pause_ms == 3000

def test_speech_rate_with_pauses_excluded():
    \"\"\"Speech rate excludes pause time\"\"\"
    analyzer = SpeechRateAnalyzer()

    # 10 words spoken over 5 seconds of actual speech
    # Total duration 10s (includes 5s pause)
    transcript = "one two three four five six seven eight nine ten"
    actual_speech_duration_ms = 5000

    result = analyzer.analyze(transcript, actual_speech_duration_ms)

    # 10 words in 5s = 120 WPM
    assert result.speech_rate_wpm == pytest.approx(120, rel=0.1)
```

### Signal Generation Tests

```python
# tests/unit/audio/test_signal_generation.py

from app.audio import AudioSignalGenerator

def test_audio_signal_structure():
    \"\"\"AudioSignal contains all required fields\"\"\"
    generator = AudioSignalGenerator()

    transcript = "The answer is dynamic programming."
    segments = [{"text": transcript, "start": 0, "end": 4500, "confidence": 0.92}]

    signal = generator.generate(
        transcript=transcript,
        segments=segments,
        pause_duration_ms=3500
    )

    assert signal.transcript == transcript
    assert signal.transcript_finalized is True
    assert signal.confidence_score > 0
    assert signal.speech_state in ["complete", "incomplete", "continuing"]
    assert signal.pause_duration_ms == 3500
    assert signal.filler_word_count >= 0
    assert signal.speech_rate_wpm > 0

def test_confidence_score_aggregation():
    \"\"\"Confidence score aggregates multiple factors\"\"\"
    generator = AudioSignalGenerator()

    # High transcription confidence, complete sentence, clear audio
    signal = generator.generate(
        transcript="Yes, that is correct.",
        segments=[{"text": "Yes, that is correct.", "confidence": 0.95}],
        audio_quality_score=0.90,
        completeness_confidence=0.88
    )

    # Aggregated confidence should be high
    assert signal.confidence_score > 0.85

def test_signal_generation_includes_metadata():
    \"\"\"Signal includes full analysis metadata\"\"\"
    generator = AudioSignalGenerator()

    signal = generator.generate(
        transcript="I think the answer is um dynamic programming.",
        segments=[],
        pause_duration_ms=3200
    )

    assert hasattr(signal, 'segments')
    assert hasattr(signal, 'audio_quality_score')
    assert hasattr(signal, 'background_noise_detected')
```

---

## 2. Integration Tests (Database + Real Components)

### Audio Analytics Repository Tests

```python
# tests/integration/audio/test_audio_analytics_repository.py

import pytest
from app.audio.persistence.repository import AudioAnalyticsRepository

@pytest.fixture
def db_with_exchanges(db_session):
    \"\"\"Create test exchanges\"\"\"
    from app.persistence.models import InterviewExchange

    exchange = InterviewExchange(
        submission_id=1,
        question_snapshot={"text": "What is dynamic programming?"},
        stage="responding"
    )
    db_session.add(exchange)
    db_session.commit()
    return db_session, exchange.id

def test_create_audio_analytics(db_with_exchanges):
    \"\"\"Create audio analytics record\"\"\"
    db_session, exchange_id = db_with_exchanges

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(
        exchange_id=exchange_id,
        transcript="The answer is dynamic programming.",
        confidence_score=0.92,
        speech_rate_wpm=145,
        filler_word_count=2,
        sentiment_score=0.35,
        pause_duration_ms=3200,
        speech_state="complete"
    )

    assert analytics.id is not None
    assert analytics.interview_exchange_id == exchange_id
    assert analytics.transcript == "The answer is dynamic programming."

def test_unique_constraint_on_exchange_id(db_with_exchanges):
    \"\"\"Only one analytics record per exchange\"\"\"
    db_session, exchange_id = db_with_exchanges

    repo = AudioAnalyticsRepository(db_session)

    # Create first record
    repo.create(exchange_id=exchange_id, transcript="First", confidence_score=0.9)

    # Attempt to create second record for same exchange
    with pytest.raises(IntegrityError):
        repo.create(exchange_id=exchange_id, transcript="Second", confidence_score=0.8)

def test_transcript_immutability_after_finalization(db_with_exchanges):
    \"\"\"Finalized transcripts cannot be updated\"\"\"
    db_session, exchange_id = db_with_exchanges

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(
        exchange_id=exchange_id,
        transcript="Original transcript",
        confidence_score=0.9
    )

    # Mark as finalized
    repo.mark_finalized(analytics.id)

    # Attempt to update transcript
    with pytest.raises(ImmutabilityError):
        repo.update_transcript(analytics.id, "Modified transcript")
```

### Transcription Pipeline Integration

```python
# tests/integration/audio/test_transcription_pipeline.py

@pytest.mark.integration
def test_full_transcription_pipeline(mock_transcription_service):
    \"\"\"Full pipeline from audio to transcript\"\"\"
    from app.audio import process_audio_stream

    # Simulate audio chunks
    audio_chunks = [
        b"audio_chunk_1",
        b"audio_chunk_2",
        b"audio_chunk_3"
    ]

    result = process_audio_stream(
        exchange_id=123,
        audio_chunks=audio_chunks,
        sample_rate=16000
    )

    assert result.transcript is not None
    assert len(result.transcript) > 0
    assert result.confidence_score > 0
    assert result.speech_state in ["complete", "incomplete"]

def test_streaming_partial_transcripts(mock_transcription_service):
    \"\"\"Streaming mode produces partial transcripts\"\"\"
    from app.audio.transcription import StreamingTranscriber

    transcriber = StreamingTranscriber()
    partials = []

    def on_partial(transcript):
        partials.append(transcript)

    transcriber.on_partial_transcript(on_partial)

    # Send chunks
    for chunk in [b"chunk1", b"chunk2", b"chunk3"]:
        transcriber.process_chunk(chunk)

    # Should have received partial updates
    assert len(partials) > 0
```

### Orchestrator Integration Tests

```python
# tests/integration/audio/test_orchestrator_integration.py

def test_audio_signal_emitted_to_orchestrator():
    \"\"\"AudioSignal properly emitted to orchestrator\"\"\"
    from app.audio import AudioModule
    from app.interview.orchestration import InterviewOrchestrator

    orchestrator = Mock(spec=InterviewOrchestrator)
    audio_module = AudioModule()

    audio_module.register_signal_handler(orchestrator.on_audio_signal)

    # Process audio
    audio_module.process_audio(
        exchange_id=123,
        audio_data=b"test audio",
        sample_rate=16000
    )

    # Orchestrator should receive signal
    orchestrator.on_audio_signal.assert_called_once()
    signal = orchestrator.on_audio_signal.call_args[0][0]
    assert signal.transcript_finalized is True

def test_orchestrator_decides_next_action_not_audio():
    \"\"\"Orchestrator decides next action, not audio module\"\"\"
    from app.audio import AudioModule

    audio_module = AudioModule()
    mock_orchestrator = Mock()

    audio_module.register_signal_handler(mock_orchestrator.on_audio_signal)

    # Audio emits signal with speech_state="complete"
    signal = audio_module.process_audio(...)

    # Audio module should NOT advance interview state
    # Only emit signal
    assert signal.speech_state == "complete"
    # Orchestrator decides what to do next
    mock_orchestrator.on_audio_signal.assert_called()
```

---

## 3. E2E Tests (Full Voice Interview Flow)

```python
# tests/e2e/audio/test_voice_interview_flow.py

@pytest.mark.e2e
def test_complete_voice_interview_flow(client, db_session):
    \"\"\"Complete voice interview from start to finish\"\"\"

    # 1. Start interview
    response = client.post("/api/v1/interviews/123/start")
    assert response.status_code == 200

    # 2. Start audio capture for first question
    response = client.post("/api/v1/interviews/123/exchanges/1/audio/start")
    assert response.status_code == 200

    # 3. Stream audio chunks
    audio_chunks = generate_test_audio_chunks("The answer is dynamic programming.")
    for chunk in audio_chunks:
        client.post("/api/v1/interviews/123/exchanges/1/audio/chunk", data=chunk)

    # 4. Silence detected, transcript finalized
    time.sleep(3.5)  # Wait for silence threshold

    # 5. Check audio analytics persisted
    analytics = db_session.query(AudioAnalytics).filter_by(interview_exchange_id=1).first()
    assert analytics is not None
    assert "dynamic programming" in analytics.transcript

    # 6. Interview proceeds to evaluation
    response = client.get("/api/v1/interviews/123/exchanges/1/status")
    assert response.json()["stage"] == "evaluating"
```

### Race Condition Tests

```python
# tests/e2e/audio/test_race_conditions.py

@pytest.mark.e2e
def test_concurrent_silence_and_new_speech():
    \"\"\"Handle race: silence expires while new speech arrives\"\"\"

    audio_module = AudioModule()

    # Send initial audio
    audio_module.process_chunk(exchange_id=123, chunk=b"audio1", timestamp=1000)

    # Wait almost to threshold
    time.sleep(2.9)

    # Send new audio just before threshold
    audio_module.process_chunk(exchange_id=123, chunk=b"audio2", timestamp=3900)

    # Verify: silence evaluation should NOT have triggered
    analytics = get_audio_analytics(exchange_id=123)
    assert analytics is None  # Not finalized yet

@pytest.mark.e2e
def test_finalization_prevents_new_audio():
    \"\"\"Cannot accept new audio after finalization\"\"\"

    audio_module = AudioModule()

    # Process and finalize
    audio_module.process_audio(exchange_id=123, audio_data=b"audio", finalize=True)

    # Attempt to send more audio
    with pytest.raises(ExchangeFinalizedError):
        audio_module.process_chunk(exchange_id=123, chunk=b"more audio")
```

---

## 4. Performance Tests

```python
# tests/performance/audio/test_latency.py

@pytest.mark.performance
def test_transcription_latency_sla():
    \"\"\"Transcription completes within 2s SLA\"\"\"
    import time
    from app.audio.transcription import Transcriber

    transcriber = Transcriber()

    audio_data = generate_test_audio(duration_seconds=5)

    start = time.time()
    result = transcriber.transcribe(audio_data)
    latency = time.time() - start

    assert latency < 2.0, f"Transcription took {latency}s, exceeds 2s SLA"
    assert result.transcript is not None

@pytest.mark.performance
def test_analysis_latency_sla():
    \"\"\"Analysis completes within 500ms SLA\"\"\"
    import time
    from app.audio.analysis import AudioAnalyzer

    analyzer = AudioAnalyzer()

    transcript = "This is a test transcript with some filler words like um and uh."

    start = time.time()
    result = analyzer.analyze(transcript)
    latency = time.time() - start

    assert latency < 0.5, f"Analysis took {latency}s, exceeds 500ms SLA"

@pytest.mark.performance
def test_end_to_end_audio_latency():
    \"\"\"Speech end to signal emission within 3s p95\"\"\"
    latencies = []

    for _ in range(100):
        start = time.time()

        # Process audio
        signal = process_audio_stream(...)

        latencies.append(time.time() - start)

    p95_latency = sorted(latencies)[94]
    assert p95_latency < 3.0, f"P95 latency {p95_latency}s exceeds 3s SLA"
```

---

## Test Coverage Requirements

- **Unit Tests:** >90% code coverage
- **Integration Tests:** All database operations + external service integration
- **E2E Tests:** Full voice interview flows including race conditions
- **Performance Tests:** Verify latency SLAs (<2s transcription, <500ms analysis, <3s total)

---

## Running Tests

```bash
# Unit tests (mocked, fast)
pytest tests/unit/audio/ -v

# Integration tests (database required)
pytest tests/integration/audio/ -v --db

# E2E tests (full stack)
pytest tests/e2e/audio/ -v --e2e

# Performance tests
pytest tests/performance/audio/ -v --performance

# Race condition tests only
pytest tests/e2e/audio/test_race_conditions.py -v

# Coverage report
pytest tests/audio/ --cov=app/audio --cov-report=html
```

---

## Critical Test Scenarios (Must Pass)

- [ ] Silence detection race condition handled correctly
- [ ] Transcript finalization prevents further updates
- [ ] Completeness classifier accuracy >85% on test set
- [ ] Exchange immutability enforced (IntegrityError on duplicate)
- [ ] AudioSignal emission happens AFTER persistence
- [ ] Concurrent audio streams do not interfere
- [ ] Transcription latency <2s p95
- [ ] Analysis latency <500ms p95
- [ ] Multi-tenancy: no cross-tenant audio access

---

**End of Audio Module Testing Guide**
