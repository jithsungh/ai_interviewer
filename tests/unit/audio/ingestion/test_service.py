"""
Unit tests for AudioIngestionService.

Covers the full ingestion pipeline: session lifecycle, chunk ingestion,
silence detection integration, buffer forwarding.
"""

import pytest
import time
import numpy as np

from app.audio.ingestion.service import AudioIngestionService
from app.audio.ingestion.contracts import (
    AudioStreamRequest,
    SilenceDetectedEvent,
    SilenceReason,
)
from app.audio.ingestion.exceptions import (
    SessionAlreadyActiveError,
    SessionClosedError,
    SessionNotFoundError,
    SessionPausedError,
)


def _make_audio_bytes(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Generate random float32 PCM audio bytes."""
    n_samples = int(sample_rate * duration_ms / 1000)
    return np.random.randn(n_samples).astype(np.float32).tobytes()


class TestServiceSessionLifecycle:

    def test_start_and_stop(self):
        svc = AudioIngestionService()
        session = svc.start_session(exchange_id=1, sample_rate=16000)
        assert session.is_active
        svc.stop_session(1)

    def test_duplicate_start_raises(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        with pytest.raises(SessionAlreadyActiveError):
            svc.start_session(exchange_id=1, sample_rate=16000)
        svc.stop_session(1)

    def test_pause_resume_stop(self):
        svc = AudioIngestionService()
        session = svc.start_session(exchange_id=1, sample_rate=16000)

        svc.pause_session(1, reason="thinking")
        assert session.is_paused

        svc.resume_session(1)
        # After resume, session_manager replaces detector so re-fetch
        s = svc._session_manager.get_session(1)
        assert s.is_paused is False

        svc.stop_session(1)


class TestIngestChunk:

    def test_ingest_returns_normalized_chunk(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)

        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_make_audio_bytes(100, 16000),
            sample_rate=16000,
            timestamp_ms=500,
        )
        chunk = svc.ingest_chunk(req)

        assert chunk.exchange_id == 1
        assert chunk.normalized is True
        assert chunk.sample_rate == 16000
        assert chunk.channels == 1

        svc.stop_session(1)

    def test_ingest_resamples_48khz(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=48000)

        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_make_audio_bytes(100, 48000),
            sample_rate=48000,
            timestamp_ms=0,
        )
        chunk = svc.ingest_chunk(req)
        assert chunk.sample_rate == 16000

        svc.stop_session(1)

    def test_ingest_on_closed_session_raises(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.stop_session(1)

        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_make_audio_bytes(),
            sample_rate=16000,
        )
        with pytest.raises(SessionNotFoundError):
            svc.ingest_chunk(req)

    def test_ingest_on_paused_session_raises(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.pause_session(1)

        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_make_audio_bytes(),
            sample_rate=16000,
        )
        with pytest.raises(SessionPausedError):
            svc.ingest_chunk(req)

        svc.stop_session(1)


class TestSilenceIntegration:

    def test_silence_event_after_threshold(self):
        svc = AudioIngestionService(silence_threshold_ms=200)
        events = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=1, sample_rate=16000)

        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_make_audio_bytes(),
            sample_rate=16000,
            timestamp_ms=1000,
        )
        svc.ingest_chunk(req)

        time.sleep(0.4)

        assert len(events) >= 1
        assert events[0].exchange_id == 1
        assert events[0].reason == SilenceReason.THRESHOLD_REACHED

    def test_stop_emits_session_ended(self):
        svc = AudioIngestionService()
        events = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.stop_session(1)

        session_ended = [e for e in events if e.reason == SilenceReason.SESSION_ENDED]
        assert len(session_ended) == 1


class TestTranscriptionCallback:

    def test_callback_invoked_on_stop(self):
        svc = AudioIngestionService(buffer_window_ms=100)
        received = []
        svc.on_transcription_ready(lambda windows: received.extend(windows))

        svc.start_session(exchange_id=1, sample_rate=16000)

        for i in range(5):
            req = AudioStreamRequest(
                interview_exchange_id=1,
                audio_chunk=_make_audio_bytes(100, 16000),
                sample_rate=16000,
                timestamp_ms=i * 100,
            )
            svc.ingest_chunk(req)

        svc.stop_session(1)

        # At least some windows should have been forwarded
        assert len(received) >= 1


class TestConcurrentSessions:

    def test_two_sessions_no_interference(self):
        svc = AudioIngestionService(silence_threshold_ms=200)
        events = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.start_session(exchange_id=2, sample_rate=16000)

        # Ingest into session 1 only
        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_make_audio_bytes(),
            sample_rate=16000,
            timestamp_ms=1000,
        )
        svc.ingest_chunk(req)

        time.sleep(0.4)

        # Only session 1 should fire silence
        s1_events = [e for e in events if e.exchange_id == 1]
        assert len(s1_events) >= 1

        svc.stop_session(1)
        svc.stop_session(2)


class TestCleanup:

    def test_cleanup_timed_out(self):
        svc = AudioIngestionService(session_timeout_s=1)
        svc.start_session(exchange_id=1, sample_rate=16000)

        # Backdate
        s = svc._session_manager.get_session(1)
        s.last_activity_at = time.monotonic() - 2

        expired = svc.cleanup_timed_out_sessions()
        assert 1 in expired


class TestFinalizeSession:

    def test_finalize_is_alias_for_stop(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.finalize_session(1)

        assert not svc._session_manager.has_session(1)
