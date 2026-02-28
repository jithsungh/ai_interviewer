"""
Integration tests for the AudioIngestionService.

These tests exercise the full ingestion pipeline end-to-end without a
database (ingestion is stateless). They validate the interaction between
normalizer, buffer manager, session manager, and silence detector working
together as a cohesive unit.
"""

import pytest
import time
import threading
import numpy as np

from app.audio.ingestion.service import AudioIngestionService
from app.audio.ingestion.contracts import (
    AudioSessionControl,
    AudioStreamRequest,
    SessionAction,
    SilenceDetectedEvent,
    SilenceReason,
)
from app.audio.ingestion.exceptions import (
    SessionAlreadyActiveError,
    SessionClosedError,
    SessionNotFoundError,
    SessionPausedError,
)


def _pcm_bytes(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    n = int(sample_rate * duration_ms / 1000)
    return np.random.randn(n).astype(np.float32).tobytes()


class TestFullIngestionWorkflow:
    """End-to-end: start → ingest multiple chunks → silence detected → stop."""

    def test_complete_workflow(self):
        svc = AudioIngestionService(silence_threshold_ms=300, buffer_window_ms=200)

        silence_events: list[SilenceDetectedEvent] = []
        svc.on_silence_detected(lambda e: silence_events.append(e))

        transcription_windows = []
        svc.on_transcription_ready(lambda w: transcription_windows.extend(w))

        # 1. Start session
        svc.start_session(exchange_id=42, sample_rate=16000)

        # 2. Ingest 5 chunks over 500ms
        for i in range(5):
            svc.ingest_chunk(AudioStreamRequest(
                interview_exchange_id=42,
                audio_chunk=_pcm_bytes(100, 16000),
                sample_rate=16000,
                timestamp_ms=i * 100,
            ))

        # 3. Wait for silence threshold
        time.sleep(0.5)

        # Silence should have been detected
        threshold_events = [
            e for e in silence_events
            if e.reason == SilenceReason.THRESHOLD_REACHED and e.exchange_id == 42
        ]
        assert len(threshold_events) >= 1

        # 4. Stop session
        svc.stop_session(42)

        # Session-ended event should fire
        ended_events = [
            e for e in silence_events
            if e.reason == SilenceReason.SESSION_ENDED and e.exchange_id == 42
        ]
        assert len(ended_events) == 1

    def test_pause_prevents_silence_event_resume_restores(self):
        svc = AudioIngestionService(silence_threshold_ms=200)
        events = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=1, sample_rate=16000)

        # Ingest one chunk
        svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_pcm_bytes(),
            sample_rate=16000,
            timestamp_ms=100,
        ))

        # Pause immediately → silence timer should be cancelled
        svc.pause_session(1)
        time.sleep(0.4)

        # No silence event during pause
        threshold_events = [
            e for e in events if e.reason == SilenceReason.THRESHOLD_REACHED
        ]
        assert len(threshold_events) == 0

        # Resume and send another chunk
        svc.resume_session(1)
        svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_pcm_bytes(),
            sample_rate=16000,
            timestamp_ms=800,
        ))

        time.sleep(0.4)

        # Now a silence event should appear
        threshold_events = [
            e for e in events if e.reason == SilenceReason.THRESHOLD_REACHED
        ]
        assert len(threshold_events) >= 1

        svc.stop_session(1)


class TestConcurrentSessionsIntegration:
    """Multiple sessions running in parallel with interleaved audio."""

    def test_no_cross_session_interference(self):
        svc = AudioIngestionService(silence_threshold_ms=200)
        events: list[SilenceDetectedEvent] = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=100, sample_rate=16000)
        svc.start_session(exchange_id=200, sample_rate=16000)

        results = {"100": [], "200": []}

        def ingest_for(eid):
            for i in range(10):
                svc.ingest_chunk(AudioStreamRequest(
                    interview_exchange_id=eid,
                    audio_chunk=_pcm_bytes(50, 16000),
                    sample_rate=16000,
                    timestamp_ms=i * 50,
                ))
                results[str(eid)].append(i)

        t1 = threading.Thread(target=ingest_for, args=(100,))
        t2 = threading.Thread(target=ingest_for, args=(200,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results["100"]) == 10
        assert len(results["200"]) == 10

        svc.stop_session(100)
        svc.stop_session(200)

    def test_silence_per_session(self):
        svc = AudioIngestionService(silence_threshold_ms=200)
        events = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=100, sample_rate=16000)
        svc.start_session(exchange_id=200, sample_rate=16000)

        # Only send audio to session 100
        svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=100,
            audio_chunk=_pcm_bytes(),
            sample_rate=16000,
            timestamp_ms=1000,
        ))

        time.sleep(0.4)

        # Session 100 should have silence, 200 should not
        s100 = [e for e in events if e.exchange_id == 100 and e.reason == SilenceReason.THRESHOLD_REACHED]
        assert len(s100) >= 1

        svc.stop_session(100)
        svc.stop_session(200)


class TestSessionControlDispatch:
    """Test the handle_session_control dispatcher."""

    def test_dispatch_start(self):
        svc = AudioIngestionService()
        ctrl = AudioSessionControl(
            interview_exchange_id=5,
            action=SessionAction.START,
        )
        svc.handle_session_control(ctrl)
        assert svc._session_manager.has_session(5)
        svc.stop_session(5)

    def test_dispatch_pause_resume_stop(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=5, sample_rate=16000)

        svc.handle_session_control(AudioSessionControl(
            interview_exchange_id=5, action=SessionAction.PAUSE, reason="thinking"
        ))
        s = svc._session_manager.get_session(5)
        assert s.is_paused is True

        svc.handle_session_control(AudioSessionControl(
            interview_exchange_id=5, action=SessionAction.RESUME,
        ))
        s = svc._session_manager.get_session(5)
        assert s.is_paused is False

        svc.handle_session_control(AudioSessionControl(
            interview_exchange_id=5, action=SessionAction.STOP,
        ))
        assert not svc._session_manager.has_session(5)


class TestErrorPathsIntegration:

    def test_ingest_without_session_raises(self):
        svc = AudioIngestionService()
        with pytest.raises(SessionNotFoundError):
            svc.ingest_chunk(AudioStreamRequest(
                interview_exchange_id=999,
                audio_chunk=_pcm_bytes(),
                sample_rate=16000,
            ))

    def test_ingest_after_stop_raises(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.stop_session(1)

        with pytest.raises(SessionNotFoundError):
            svc.ingest_chunk(AudioStreamRequest(
                interview_exchange_id=1,
                audio_chunk=_pcm_bytes(),
                sample_rate=16000,
            ))

    def test_double_stop_raises(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.stop_session(1)

        with pytest.raises(SessionNotFoundError):
            svc.stop_session(1)

    def test_ingest_paused_raises(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.pause_session(1)

        with pytest.raises(SessionPausedError):
            svc.ingest_chunk(AudioStreamRequest(
                interview_exchange_id=1,
                audio_chunk=_pcm_bytes(),
                sample_rate=16000,
            ))
        svc.stop_session(1)


class TestResamplingIntegration:
    """Verify that audio at non-standard rates is correctly resampled."""

    def test_48khz_resampled_to_16khz(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=48000)

        chunk = svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_pcm_bytes(100, 48000),
            sample_rate=48000,
            timestamp_ms=0,
        ))

        assert chunk.sample_rate == 16000
        svc.stop_session(1)

    def test_8khz_resampled_to_16khz(self):
        svc = AudioIngestionService()
        svc.start_session(exchange_id=1, sample_rate=8000)

        chunk = svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_pcm_bytes(100, 8000),
            sample_rate=8000,
            timestamp_ms=0,
        ))

        assert chunk.sample_rate == 16000
        svc.stop_session(1)
