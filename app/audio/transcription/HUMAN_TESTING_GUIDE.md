# Human Testing Guide — `audio/transcription`

## Overview

The transcription module is a **stateless** speech-to-text service.  It has no
database tables, no migrations, and no persistent state.  It converts raw audio
bytes into text via external (Whisper, Google) or local (openai-whisper) STT
providers.

---

## Prerequisites

| Item | Required | Notes |
|------|----------|-------|
| Running FastAPI server | Yes | `uvicorn app.bootstrap.app:create_app --factory --reload` |
| Valid auth token | Yes | All endpoints require `get_identity` (see `app/auth`) |
| OpenAI API key | Whisper provider | `OPENAI_API_KEY` env var or `LLM_API_KEY` |
| Google Cloud credentials | Google provider | `GOOGLE_CLOUD_API_KEY` env var |
| `openai-whisper` package | Local provider | `pip install openai-whisper` |

### Environment variables

```bash
# Provider selection (whisper | google | local)
export AUDIO_TRANSCRIPTION_PROVIDER=whisper

# API keys
export OPENAI_API_KEY=sk-...
# export GOOGLE_CLOUD_API_KEY=...

# Tuning (optional)
export TRANSCRIPTION_MAX_RETRIES=3
export TRANSCRIPTION_RETRY_DELAY_S=2.0
export TRANSCRIPTION_TIMEOUT_S=10.0
export WHISPER_MODEL=base.en         # local provider only
```

---

## Endpoints

Base URL: `http://localhost:8000/api/v1/audio/transcription`

### 1. `POST /transcribe` — Batch Transcription

Transcribes Base64-encoded audio.  Primarily for manual testing and admin
diagnostics (the production path uses the internal ingestion → transcription
callback).

**Request:**

```json
{
  "audio_base64": "<base64-encoded 16 kHz mono PCM/WAV>",
  "sample_rate": 16000,
  "language": "en",
  "context": "technical interview",
  "provider": "whisper"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audio_base64` | string | **Yes** | — | Base64-encoded audio data |
| `sample_rate` | int | No | `16000` | Audio sample rate (Hz) |
| `language` | string | No | `null` | ISO 639-1 language hint |
| `context` | string | No | `null` | Contextual hint (max 256 chars) |
| `provider` | string | No | `null` | Override: `whisper`, `google`, or `local` |

**Successful response (200):**

```json
{
  "transcript": "The answer is dynamic programming.",
  "confidence_score": 0.93,
  "language_detected": "en",
  "segments": [
    {
      "text": "The answer",
      "start_ms": 0,
      "end_ms": 500,
      "confidence": 0.95
    },
    {
      "text": "is dynamic programming",
      "start_ms": 500,
      "end_ms": 1700,
      "confidence": 0.91
    }
  ],
  "provider": "whisper"
}
```

**Error responses:**

| Code | Cause |
|------|-------|
| 400 | Invalid base64 data, missing required field |
| 401 | Missing or invalid auth token |
| 502 | STT provider failed / unreachable |
| 504 | Transcription timed out |

### 2. `GET /health` — Provider Health Check

Returns the configured provider and its readiness.

**Response (200):**

```json
{
  "provider": "whisper",
  "status": "configured",
  "message": "Transcription provider 'whisper' is configured"
}
```

---

## curl Examples

### Prepare audio

```bash
# Generate 1 second of silent 16 kHz mono PCM and encode to base64
python3 -c "
import base64, struct
pcm = struct.pack('<' + 'h' * 16000, *([0] * 16000))
print(base64.b64encode(pcm).decode())
" > /tmp/audio_b64.txt
```

### Transcribe (Whisper)

```bash
AUTH_TOKEN="<your-jwt-token>"

curl -s -X POST http://localhost:8000/api/v1/audio/transcription/transcribe \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_base64\": \"$(cat /tmp/audio_b64.txt)\",
    \"sample_rate\": 16000,
    \"language\": \"en\"
  }" | python3 -m json.tool
```

### Transcribe with provider override

```bash
curl -s -X POST http://localhost:8000/api/v1/audio/transcription/transcribe \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_base64\": \"$(cat /tmp/audio_b64.txt)\",
    \"sample_rate\": 16000,
    \"provider\": \"local\"
  }" | python3 -m json.tool
```

### Health check

```bash
curl -s http://localhost:8000/api/v1/audio/transcription/health \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

---

## Manual Verification Checklist

### Happy path

- [ ] `POST /transcribe` returns 200 with `transcript`, `confidence_score`, `segments`
- [ ] `GET /health` returns 200 with `provider` and `status`
- [ ] Provider override via `"provider": "local"` switches the engine
- [ ] Segments contain `text`, `start_ms`, `end_ms`, `confidence`

### Error path

- [ ] Invalid base64 → 400 `"Invalid base64 audio data"`
- [ ] Empty `audio_base64` → 422 validation error
- [ ] No auth header → 401
- [ ] Invalid provider name in config → 400 `ProviderNotFoundError`
- [ ] Provider API failure (revoke key) → 502 `TranscriptionError`

### Internal (programmatic) path

The primary production usage is via the `TranscriptionService` called by the
ingestion module's callback.  To verify this path:

```python
from app.audio.transcription.service import TranscriptionService
from app.audio.transcription.contracts import TranscriptionRequest

svc = TranscriptionService(provider="whisper", api_key="sk-...")
req = TranscriptionRequest(audio_data=b"\x00" * 16000, sample_rate=16000)

result = await svc.transcribe(req)
print(result.transcript, result.confidence_score)
```

### Fallback chain

```python
result = await svc.transcribe_with_fallback(req)
# Falls back to secondary providers if primary fails
```

---

## Schema & Migration Notes

**No database changes required.**  Transcription is a stateless service — it
converts audio bytes to text and returns the result.  Transcripts are persisted
downstream by the `audio.persistence` module (not implemented yet).

---

## Automated Tests

```bash
# Unit tests (82 tests)
python -m pytest tests/unit/audio/transcription/ -v

# Integration tests (10 tests)
python -m pytest tests/integration/audio/transcription/ -v

# All audio transcription tests
python -m pytest tests/unit/audio/transcription/ tests/integration/audio/transcription/ -v
```
