# Audio Transcription Module

**See Also:** [Clarifications Architecture](../../docs/CLARIFICATIONS-ARCHITECTURE.md) - High-level overview of intent classification and how ASR confidence impacts it.

## 1. Purpose

**Why this submodule exists:**

The Audio Transcription module converts speech audio into text transcripts using external speech-to-text (STT) engines. It:

- Abstracts multiple STT providers (OpenAI Whisper, Google Cloud Speech, Azure Speech, AssemblyAI)
- Supports **streaming transcription** (partial transcripts during speech)
- Supports **batch transcription** (final transcript after silence)
- Provides **confidence scores** for transcript quality
- Handles **multi-language detection** (if candidate speaks non-English)
- Returns **word-level timestamps** for analysis (pause detection, speech rate)

**Critical responsibility:** Transcription must be **provider-agnostic** so tenants can choose their preferred STT engine or use local models for data sovereignty.

---

## 2. Owned Tables / Entities

**None.** This module is stateless. All transcripts are persisted by the `audio.persistence` module to `audio_analytics`.

---

## 3. Input Contracts

### TranscriptionRequest

```python
@dataclass
class TranscriptionRequest:
    audio_data: bytes                # REQUIRED: Audio chunk(s) to transcribe
    sample_rate: int                 # REQUIRED: Audio sample rate (usually 16kHz)
    language: Optional[str] = None   # Optional: ISO 639-1 code (e.g., "en", "es")
    context: Optional[str] = None    # Optional: Context for better accuracy (e.g., "coding interview")
    streaming: bool = False          # True for partial transcripts, False for final
```

### TranscriptionConfig

```python
@dataclass
class TranscriptionConfig:
    provider: Literal["whisper", "google", "azure", "assemblyai", "local"]
    api_key: Optional[str] = None          # For external providers
    model: Optional[str] = None            # e.g., "whisper-1", "base.en"
    language: Optional[str] = None         # Force language (or auto-detect)
    detect_language: bool = True           # Auto-detect if True
    word_timestamps: bool = True           # Return word-level timestamps
    profanity_filter: bool = False         # Filter profanity (usually disabled for interviews)
```

---

## 4. Output Contracts

### TranscriptionResult

```python
@dataclass
class TranscriptionResult:
    transcript: str                        # Full transcript text
    confidence_score: float                # 0.0-1.0 (aggregate confidence)
    language_detected: Optional[str] = None  # ISO 639-1 code if detected
    segments: List[TranscriptSegment] = []   # Word-level segments
    partial: bool = False                    # True if streaming partial result
    provider_metadata: Dict[str, Any] = {}   # Provider-specific data
```

### TranscriptSegment

```python
@dataclass
class TranscriptSegment:
    text: str                # Word or phrase
    start_ms: int            # Start timestamp (milliseconds)
    end_ms: int              # End timestamp
    confidence: float        # 0.0-1.0 (per-segment confidence)
```

---

## 5. Acceptance Criteria

### Functional Requirements

1. **Provider Abstraction:**
   - Support at least 3 external providers: OpenAI Whisper, Google Cloud Speech, Azure Speech
   - Support local Whisper model for data sovereignty
   - Swappable via configuration (no code changes)

2. **Streaming Transcription:**
   - Emit partial transcripts as audio chunks arrive
   - Update partial transcripts with more accurate final transcripts

3. **Batch Transcription:**
   - Process full audio buffer after silence detected
   - Return final transcript with high confidence

4. **Confidence Scoring:**
   - Aggregate confidence from per-word confidence scores
   - Flag low-confidence transcripts (<0.6) for manual review

5. **Language Detection:**
   - Auto-detect language if not specified
   - Support English, Spanish, French, German, Hindi (common interview languages)

6. **Word-Level Timestamps:**
   - Return start/end timestamps for each word
   - Used by `analysis` module for speech rate, pause detection

### Non-Functional Requirements

1. **Latency:** <2s p95 for transcription (from audio end to transcript return)
2. **Accuracy:** >90% word accuracy for clear audio (per provider benchmarks)
3. **Retry Logic:** Retry failed transcriptions up to 3 times with exponential backoff
4. **Cost Tracking:** Log transcription duration, provider, cost estimate for cost monitoring

---

## 6. Invariants & Constraints

### Must Hold

1. **Provider Config Must Be Valid:** Cannot transcribe without valid API key (if external provider)
2. **Audio Must Be 16kHz Mono:** Transcription assumes normalized audio (from `ingestion` module)
3. **Streaming Mode Requires Real-Time Provider:** Not all providers support streaming (e.g., Whisper API is batch-only)
4. **Confidence Score Between 0.0-1.0:** Always normalized across providers

### Forbidden

- MUST NOT store audio files to disk (GDPR: audio is ephemeral)
- MUST NOT modify transcripts after returning (immutability)
- MUST NOT block on external API calls (use async/await)
- MUST NOT expose provider API keys in logs or responses

---

## 7. Provider Implementations

### OpenAI Whisper (Batch Only)

```python
class WhisperTranscriber(Transcriber):
    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        import openai

        # Whisper API expects audio file
        audio_file = io.BytesIO(request.audio_data)
        audio_file.name = "audio.wav"

        response = await openai.Audio.atranscribe(
            model="whisper-1",
            file=audio_file,
            language=request.language,
            response_format="verbose_json"  # Get word timestamps
        )

        return TranscriptionResult(
            transcript=response["text"],
            confidence_score=self._calculate_confidence(response),
            language_detected=response.get("language"),
            segments=self._parse_segments(response["segments"]),
            provider_metadata={"model": "whisper-1"}
        )
```

### Google Cloud Speech (Streaming Supported)

```python
class GoogleSpeechTranscriber(Transcriber):
    async def transcribe_streaming(self, audio_stream) -> AsyncIterator[TranscriptionResult]:
        from google.cloud import speech

        client = speech.SpeechAsyncClient()

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True  # Partial transcripts
        )

        async for response in client.streaming_recognize(streaming_config, audio_stream):
            for result in response.results:
                yield TranscriptionResult(
                    transcript=result.alternatives[0].transcript,
                    confidence_score=result.alternatives[0].confidence,
                    segments=self._parse_google_words(result.alternatives[0].words),
                    partial=not result.is_final
                )
```

### Local Whisper (Privacy/Sovereignty)

```python
class LocalWhisperTranscriber(Transcriber):
    def __init__(self):
        import whisper
        self.model = whisper.load_model("base.en")  # Or "small", "medium"

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        # Run in thread pool (Whisper is CPU-bound)
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            request.audio_data
        )

        return result

    def _transcribe_sync(self, audio_data: bytes) -> TranscriptionResult:
        import numpy as np

        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        result = self.model.transcribe(
            audio_np,
            language="en",
            word_timestamps=True
        )

        return TranscriptionResult(
            transcript=result["text"],
            confidence_score=self._estimate_confidence(result),
            segments=self._parse_whisper_segments(result["segments"]),
            provider_metadata={"model": "base.en", "local": True}
        )
```

---

## 8. Integration Points

### Upstream (Callers)

1. **Ingestion Module (`app.audio.ingestion`):**
   - Sends normalized audio chunks for transcription
   - Receives `TranscriptionResult` (partial or final)

### Downstream (Dependencies)

1. **External APIs:**
   - OpenAI Whisper API
   - Google Cloud Speech API
   - Azure Speech API
   - AssemblyAI API

2. **Local Models:**
   - OpenAI Whisper (local via `openai-whisper` package)

3. **AI Module (`app.ai`):**
   - Uses AI module's telemetry to log transcription metadata (provider, duration, cost)

---

## 9. Edge Cases to Handle

1. **Transcription API Unavailable:**
   - Retry up to 3 times with exponential backoff (2s, 4s, 8s)
   - If all retries fail, return low-confidence transcript or error

2. **Audio Quality Too Poor:**
   - If confidence score <0.4, flag for manual review
   - Return partial transcript with warning

3. **Non-English Speech:**
   - Auto-detect language
   - If unsupported language, return error with detected language code

4. **Extremely Long Audio (>5 minutes):**
   - Chunk into smaller segments (most providers have duration limits)
   - Concatenate transcripts

5. **Profanity in Transcript:**
   - By default, do NOT filter (candidate may use technical terms that sound like profanity)
   - If tenant enables `profanity_filter`, apply provider-specific filtering

6. **Empty Audio (Silence):**
   - Return empty transcript with confidence=1.0 (correctly detected silence)

7. **Provider Rate Limit:**
   - Respect rate limits (e.g., Whisper: 50 requests/min)
   - Queue requests if needed

---

## 10. Example Usage

### Batch Transcription

```python
from app.audio.transcription import TranscriptionService

service = TranscriptionService(provider="whisper")

# Transcribe audio buffer
result = await service.transcribe(TranscriptionRequest(
    audio_data=audio_buffer,
    sample_rate=16000,
    language="en",
    context="coding interview"
))

print(result.transcript)  # "The answer is dynamic programming."
print(result.confidence_score)  # 0.92
```

### Streaming Transcription

```python
service = TranscriptionService(provider="google")

async for partial_result in service.transcribe_streaming(audio_stream):
    if partial_result.partial:
        print(f"Partial: {partial_result.transcript}")
    else:
        print(f"Final: {partial_result.transcript}")
```

### Provider Fallback

```python
service = TranscriptionService(
    providers=["whisper", "google", "local"],  # Fallback order
    fallback_enabled=True
)

# If Whisper fails, try Google, then local
result = await service.transcribe_with_fallback(request)
```

---

## 11. Configuration

### Environment Variables

```bash
# Primary provider
TRANSCRIPTION_PROVIDER=whisper  # whisper | google | azure | assemblyai | local

# API keys (for external providers)
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_API_KEY=...
AZURE_SPEECH_API_KEY=...
ASSEMBLYAI_API_KEY=...

# Local Whisper model
WHISPER_MODEL=base.en  # tiny.en | base.en | small.en | medium.en | large

# Language detection
TRANSCRIPTION_AUTO_DETECT_LANGUAGE=true
TRANSCRIPTION_DEFAULT_LANGUAGE=en

# Retry configuration
TRANSCRIPTION_MAX_RETRIES=3
TRANSCRIPTION_RETRY_DELAY_S=2

# Performance
TRANSCRIPTION_TIMEOUT_S=10
TRANSCRIPTION_CHUNK_DURATION_S=30  # Max audio duration per request
```

---

## 12. Future Enhancements

1. **Custom Vocabulary:**
   - Allow tenants to provide custom technical terms (e.g., "Kubernetes", "PostgreSQL")
   - Improves accuracy for domain-specific interviews

2. **Speaker Diarization:**
   - Detect multiple speakers (interviewer vs interviewee)
   - Useful if interviewer asks clarifying questions

3. **Real-Time Transcript Correction:**
   - Use LLM to correct obvious transcription errors (e.g., "dynamic programming" transcribed as "dynamic program in")

4. **Acoustic Model Fine-Tuning:**
   - Fine-tune local Whisper model on interview audio for better accuracy

5. **Cost Optimization:**
   - Use cheaper providers for low-stakes interviews
   - Use premium providers for high-stakes (e.g., final rounds)

6. **Multi-Language Interviews:**
   - Auto-switch transcription language mid-interview if candidate switches languages

---

**End of Audio Transcription Module Requirements**
