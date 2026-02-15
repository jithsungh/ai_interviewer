# Audio Transcription Module Testing Guide

## Testing Philosophy

Transcription testing focuses on **provider abstraction** and **graceful degradation**. Most tests use **mocked external APIs** to avoid costs and ensure deterministic results.

Key test areas:

1. **Provider swapping** (Whisper → Google → Local fallback)
2. **Confidence score accuracy** (aggregate word-level confidence)
3. **Streaming vs batch** modes
4. **Retry logic** (API failures)
5. **Language detection** (auto-detect vs forced)

---

## Test Structure

```
tests/
├── unit/
│   └── audio/
│       └── transcription/
│           ├── test_whisper_transcriber.py
│           ├── test_google_transcriber.py
│           ├── test_local_whisper.py
│           ├── test_confidence_calculator.py
│           └── test_provider_selector.py
└── integration/
    └── audio/
        └── transcription/
            ├── test_transcription_service.py
            ├── test_streaming_transcription.py
            └── test_provider_fallback.py
```

---

## 1. Unit Tests (Mocked Providers)

### Whisper Transcriber Tests

```python
# tests/unit/audio/transcription/test_whisper_transcriber.py

import pytest
from unittest.mock import AsyncMock, patch
from app.audio.transcription.whisper import WhisperTranscriber

@pytest.fixture
def mock_openai():
    with patch('openai.Audio.atranscribe') as mock:
        mock.return_value = {
            "text": "The answer is dynamic programming.",
            "language": "en",
            "segments": [
                {"text": "The", "start": 0.0, "end": 0.2, "confidence": 0.95},
                {"text": "answer", "start": 0.2, "end": 0.5, "confidence": 0.92},
                {"text": "is", "start": 0.5, "end": 0.7, "confidence": 0.98},
                {"text": "dynamic", "start": 0.7, "end": 1.1, "confidence": 0.89},
                {"text": "programming", "start": 1.1, "end": 1.7, "confidence": 0.91}
            ]
        }
        yield mock

@pytest.mark.asyncio
async def test_whisper_batch_transcription(mock_openai):
    \"\"\"Whisper batch transcription with word timestamps\"\"\"
    transcriber = WhisperTranscriber(api_key="test_key")

    result = await transcriber.transcribe(TranscriptionRequest(
        audio_data=b"fake_audio_data",
        sample_rate=16000,
        language="en"
    ))

    assert result.transcript == "The answer is dynamic programming."
    assert result.language_detected == "en"
    assert len(result.segments) == 5
    assert result.confidence_score > 0.9

@pytest.mark.asyncio
async def test_whisper_confidence_calculation(mock_openai):
    \"\"\"Whisper confidence aggregated from segments\"\"\"
    transcriber = WhisperTranscriber(api_key="test_key")

    result = await transcriber.transcribe(TranscriptionRequest(
        audio_data=b"audio",
        sample_rate=16000
    ))

    # Confidence should be mean of segment confidences
    expected_confidence = (0.95 + 0.92 + 0.98 + 0.89 + 0.91) / 5
    assert result.confidence_score == pytest.approx(expected_confidence, abs=0.01)

@pytest.mark.asyncio
async def test_whisper_api_failure_raises_exception(mock_openai):
    \"\"\"Whisper API failure raises TranscriptionError\"\"\"
    mock_openai.side_effect = Exception("API Error")

    transcriber = WhisperTranscriber(api_key="test_key")

    with pytest.raises(TranscriptionError):
        await transcriber.transcribe(TranscriptionRequest(
            audio_data=b"audio",
            sample_rate=16000
        ))

@pytest.mark.asyncio
async def test_whisper_no_streaming_support(mock_openai):
    \"\"\"Whisper does not support streaming\"\"\"
    transcriber = WhisperTranscriber(api_key="test_key")

    with pytest.raises(UnsupportedFeatureError):
        async for _ in transcriber.transcribe_streaming(audio_stream):
            pass
```

### Google Cloud Speech Tests

```python
# tests/unit/audio/transcription/test_google_transcriber.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.audio.transcription.google import GoogleSpeechTranscriber

@pytest.fixture
def mock_google_client():
    with patch('google.cloud.speech.SpeechAsyncClient') as mock:
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(
                alternatives=[
                    MagicMock(
                        transcript="The answer is",
                        confidence=0.88,
                        words=[]
                    )
                ],
                is_final=False
            )
        ]

        mock.return_value.streaming_recognize = AsyncMock(return_value=[mock_response])
        yield mock

@pytest.mark.asyncio
async def test_google_streaming_transcription(mock_google_client):
    \"\"\"Google Cloud Speech streaming mode\"\"\"
    transcriber = GoogleSpeechTranscriber(api_key="test_key")

    results = []
    async for result in transcriber.transcribe_streaming(audio_stream=b"audio"):
        results.append(result)

    assert len(results) > 0
    assert any(r.partial for r in results)  # At least one partial result

@pytest.mark.asyncio
async def test_google_final_transcript_not_partial(mock_google_client):
    \"\"\"Final transcript from Google has partial=False\"\"\"
    # Update mock to return final result
    mock_google_client.return_value.streaming_recognize.return_value[0].results[0].is_final = True

    transcriber = GoogleSpeechTranscriber(api_key="test_key")

    async for result in transcriber.transcribe_streaming(audio_stream=b"audio"):
        if not result.partial:
            assert result.confidence_score > 0
            assert len(result.transcript) > 0

@pytest.mark.asyncio
async def test_google_word_timestamps(mock_google_client):
    \"\"\"Google returns word-level timestamps\"\"\"
    # Mock word timestamps
    mock_word = MagicMock()
    mock_word.word = "dynamic"
    mock_word.start_time.total_seconds.return_value = 0.5
    mock_word.end_time.total_seconds.return_value = 0.9
    mock_word.confidence = 0.92

    mock_google_client.return_value.streaming_recognize.return_value[0].results[0].alternatives[0].words = [mock_word]

    transcriber = GoogleSpeechTranscriber(api_key="test_key")

    async for result in transcriber.transcribe_streaming(audio_stream=b"audio"):
        if result.segments:
            segment = result.segments[0]
            assert segment.text == "dynamic"
            assert segment.start_ms == 500
            assert segment.end_ms == 900
```

### Local Whisper Tests

```python
# tests/unit/audio/transcription/test_local_whisper.py

import pytest
from unittest.mock import patch, MagicMock
from app.audio.transcription.local_whisper import LocalWhisperTranscriber

@pytest.fixture
def mock_whisper_model():
    with patch('whisper.load_model') as mock_load:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Local transcription result",
            "segments": [
                {
                    "text": "Local",
                    "start": 0.0,
                    "end": 0.3,
                    "confidence": 0.90
                },
                {
                    "text": "transcription",
                    "start": 0.3,
                    "end": 0.9,
                    "confidence": 0.88
                }
            ]
        }
        mock_load.return_value = mock_model
        yield mock_model

@pytest.mark.asyncio
async def test_local_whisper_transcription(mock_whisper_model):
    \"\"\"Local Whisper model transcription\"\"\"
    transcriber = LocalWhisperTranscriber(model="base.en")

    result = await transcriber.transcribe(TranscriptionRequest(
        audio_data=b"audio",
        sample_rate=16000
    ))

    assert result.transcript == "Local transcription result"
    assert result.provider_metadata["local"] is True

@pytest.mark.asyncio
async def test_local_whisper_runs_in_executor(mock_whisper_model):
    \"\"\"Local Whisper runs in thread pool (CPU-bound)\"\"\"
    with patch('asyncio.get_event_loop') as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value=TranscriptionResult(transcript="test", confidence_score=0.9)
        )

        transcriber = LocalWhisperTranscriber(model="base.en")
        result = await transcriber.transcribe(TranscriptionRequest(audio_data=b"audio", sample_rate=16000))

        # verify run_in_executor was called
        mock_loop.return_value.run_in_executor.assert_called_once()

@pytest.mark.asyncio
async def test_local_whisper_no_api_key_required(mock_whisper_model):
    \"\"\"Local Whisper does not require API key\"\"\"
    transcriber = LocalWhisperTranscriber(model="base.en")

    # Should not raise exception
    result = await transcriber.transcribe(TranscriptionRequest(audio_data=b"audio", sample_rate=16000))

    assert result is not None
```

### Confidence Calculator Tests

```python
# tests/unit/audio/transcription/test_confidence_calculator.py

from app.audio.transcription.confidence import calculate_aggregate_confidence

def test_aggregate_confidence_mean():
    \"\"\"Aggregate confidence is mean of segment confidences\"\"\"
    segments = [
        TranscriptSegment(text="The", confidence=0.9),
        TranscriptSegment(text="answer", confidence=0.85),
        TranscriptSegment(text="is", confidence=0.95)
    ]

    confidence = calculate_aggregate_confidence(segments)

    expected = (0.9 + 0.85 + 0.95) / 3
    assert confidence == pytest.approx(expected, abs=0.01)

def test_aggregate_confidence_weighted_by_duration():
    \"\"\"Longer segments weighted more heavily\"\"\"
    segments = [
        TranscriptSegment(text="The", start_ms=0, end_ms=100, confidence=0.9),  # 100ms
        TranscriptSegment(text="answer", start_ms=100, end_ms=500, confidence=0.6),  # 400ms
    ]

    confidence = calculate_aggregate_confidence(segments, weighted=True)

    # Weighted: (0.9*100 + 0.6*400) / 500
    expected = (0.9 * 100 + 0.6 * 400) / 500
    assert confidence == pytest.approx(expected, abs=0.01)

def test_empty_segments_confidence_zero():
    \"\"\"Empty segments return confidence 0.0\"\"\"
    confidence = calculate_aggregate_confidence([])
    assert confidence == 0.0
```

### Provider Selector Tests

```python
# tests/unit/audio/transcription/test_provider_selector.py

from app.audio.transcription.provider_selector import TranscriptionProviderSelector

def test_select_provider_by_name():
    \"\"\"Select provider by name\"\"\"
    selector = TranscriptionProviderSelector()

    provider = selector.get_provider("whisper", api_key="test_key")

    assert isinstance(provider, WhisperTranscriber)

def test_provider_not_found_raises_error():
    \"\"\"Unknown provider raises error\"\"\"
    selector = TranscriptionProviderSelector()

    with pytest.raises(ProviderNotFoundError):
        selector.get_provider("unknown_provider")

def test_provider_requires_api_key():
    \"\"\"External providers require API key\"\"\"
    selector = TranscriptionProviderSelector()

    with pytest.raises(ConfigurationError):
        selector.get_provider("whisper", api_key=None)

def test_local_provider_no_api_key():
    \"\"\"Local provider does not require API key\"\"\"
    selector = TranscriptionProviderSelector()

    provider = selector.get_provider("local", api_key=None)

    assert isinstance(provider, LocalWhisperTranscriber)
```

---

## 2. Integration Tests (Real Providers)

### Transcription Service Tests

```python
# tests/integration/audio/transcription/test_transcription_service.py

import pytest
from app.audio.transcription import TranscriptionService

@pytest.mark.integration
@pytest.mark.requires_openai
async def test_whisper_real_transcription():
    \"\"\"Real Whisper API transcription (costs money)\"\"\"
    service = TranscriptionService(provider="whisper", api_key=os.getenv("OPENAI_API_KEY"))

    # Use short test audio
    audio_data = generate_test_audio("Hello world")

    result = await service.transcribe(TranscriptionRequest(
        audio_data=audio_data,
        sample_rate=16000
    ))

    assert "hello" in result.transcript.lower()
    assert result.confidence_score > 0.7

@pytest.mark.integration
async def test_transcription_retry_on_failure():
    \"\"\"Transcription retries on API failure\"\"\"
    service = TranscriptionService(
        provider="whisper",
        api_key="test_key",
        max_retries=3,
        retry_delay_s=0.1  # Short delay for testing
    )

    # Mock API to fail twice then succeed
    with patch('openai.Audio.atranscribe') as mock_api:
        mock_api.side_effect = [
            Exception("API Error"),
            Exception("API Error"),
            {"text": "Success", "segments": []}
        ]

        result = await service.transcribe(TranscriptionRequest(audio_data=b"audio", sample_rate=16000))

        assert result.transcript == "Success"
        assert mock_api.call_count == 3  # 2 failures + 1 success

@pytest.mark.integration
async def test_transcription_timeout():
    \"\"\"Transcription times out if too slow\"\"\"
    service = TranscriptionService(provider="whisper", api_key="test_key", timeout_s=1)

    with patch('openai.Audio.atranscribe') as mock_api:
        # Simulate slow API
        async def slow_transcribe(*args, **kwargs):
            await asyncio.sleep(2)
            return {"text": "Too slow", "segments": []}

        mock_api.side_effect = slow_transcribe

        with pytest.raises(TimeoutError):
            await service.transcribe(TranscriptionRequest(audio_data=b"audio", sample_rate=16000))
```

### Streaming Transcription Tests

```python
# tests/integration/audio/transcription/test_streaming_transcription.py

@pytest.mark.integration
async def test_streaming_partial_updates():
    \"\"\"Streaming mode produces partial updates\"\"\"
    service = TranscriptionService(provider="google", api_key="test_key")

    partials = []
    finals = []

    async for result in service.transcribe_streaming(audio_stream):
        if result.partial:
            partials.append(result.transcript)
        else:
            finals.append(result.transcript)

    # Should have received partial updates
    assert len(partials) > 0
    # Final transcript should be most accurate
    assert len(finals) == 1

@pytest.mark.integration
async def test_streaming_transcript_refinement():
    \"\"\"Streaming transcripts refine over time\"\"\"
    service = TranscriptionService(provider="google", api_key="test_key")

    transcripts = []

    async for result in service.transcribe_streaming(audio_stream):
        transcripts.append(result.transcript)

    # Later transcripts should be longer/more accurate
    assert len(transcripts[-1]) >= len(transcripts[0])
```

### Provider Fallback Tests

```python
# tests/integration/audio/transcription/test_provider_fallback.py

@pytest.mark.integration
async def test_fallback_to_secondary_provider():
    \"\"\"Falls back to secondary provider on primary failure\"\"\"
    service = TranscriptionService(
        providers=["whisper", "google"],
        fallback_enabled=True
    )

    # Mock Whisper to fail
    with patch('openai.Audio.atranscribe') as mock_whisper:
        mock_whisper.side_effect = Exception("Whisper failed")

        # Google should succeed
        with patch('google.cloud.speech.SpeechAsyncClient') as mock_google:
            # ... mock Google to succeed

            result = await service.transcribe_with_fallback(TranscriptionRequest(audio_data=b"audio", sample_rate=16000))

            assert result.provider_metadata["provider"] == "google"

@pytest.mark.integration
async def test_fallback_exhausted_raises_error():
    \"\"\"Raises error if all providers fail\"\"\"
    service = TranscriptionService(
        providers=["whisper", "google", "local"],
        fallback_enabled=True
    )

    # Mock all providers to fail
    with patch('openai.Audio.atranscribe', side_effect=Exception("Whisper failed")):
        with patch('google.cloud.speech.SpeechAsyncClient', side_effect=Exception("Google failed")):
            with patch('whisper.load_model', side_effect=Exception("Local failed")):

                with pytest.raises(TranscriptionError):
                    await service.transcribe_with_fallback(TranscriptionRequest(audio_data=b"audio", sample_rate=16000))
```

---

## Test Coverage Requirements

- **Unit Tests:** >90% code coverage
- **Integration Tests:** At least 1 real API call per provider (in CI/CD, costs acceptable)
- **Provider Fallback:** Must test all fallback paths

---

## Running Tests

```bash
# Unit tests (mocked, fast)
pytest tests/unit/audio/transcription/ -v

# Integration tests (real APIs, costs money)
pytest tests/integration/audio/transcription/ -v --integration --requires-openai

# Specific provider tests
pytest tests/unit/audio/transcription/test_whisper_transcriber.py -v

# Coverage
pytest tests/audio/transcription/ --cov=app/audio/transcription --cov-report=html
```

---

## Critical Tests (Must Pass)

- [ ] Whisper API transcription returns confidence score
- [ ] Google Cloud Speech streaming mode works
- [ ] Local Whisper runs in thread pool (async)
- [ ] Provider fallback works (primary fail → secondary success)
- [ ] Retry logic retries 3 times with exponential backoff
- [ ] Transcription times out after configured timeout
- [ ] Confidence score aggregated correctly from segments
- [ ] Empty audio returns empty transcript with confidence=1.0

---

**End of Audio Transcription Module Testing Guide**
