"""
Integration tests for concurrent audio sessions.

Validates that multiple sessions running in parallel do not interfere
with each other's silence detectors, buffers, or lifecycle state.
"""

import pytest
import threading
import time
import numpy as np

from app.audio.ingestion.service import AudioIngestionService
from app.audio.ingestion.contracts import (
    AudioStreamRequest,
    SilenceDetectedEvent,
    SilenceReason,
)


def _pcm(duration_ms: int = 50, rate: int = 16000) -> bytes:
    n = int(rate * duration_ms / 1000)
    return np.random.randn(n).astype(np.float32).tobytes()


class TestConcurrentSessionIsolation:

    def test_many_sessions_parallel_ingest(self):
        """10 sessions ingesting audio concurrently without error."""
        svc = AudioIngestionService(silence_threshold_ms=500)
        exchange_ids = list(range(1, 11))

        for eid in exchange_ids:
            svc.start_session(exchange_id=eid, sample_rate=16000)

        errors = []

        def ingest(eid):
            try:
                for i in range(20):
                    svc.ingest_chunk(AudioStreamRequest(
                        interview_exchange_id=eid,
                        audio_chunk=_pcm(25),
                        sample_rate=16000,
                        timestamp_ms=i * 25,
                    ))
            except Exception as exc:
                errors.append((eid, exc))

        threads = [threading.Thread(target=ingest, args=(eid,)) for eid in exchange_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent ingest: {errors}"

        for eid in exchange_ids:
            svc.stop_session(eid)

    def test_independent_silence_detectors(self):
        """Each session's silence detector fires independently."""
        svc = AudioIngestionService(silence_threshold_ms=200)
        events: list[SilenceDetectedEvent] = []
        svc.on_silence_detected(lambda e: events.append(e))

        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.start_session(exchange_id=2, sample_rate=16000)

        # Send audio to session 1
        svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=_pcm(),
            sample_rate=16000,
            timestamp_ms=100,
        ))

        # Send audio to session 2 (different timestamp)
        svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=2,
            audio_chunk=_pcm(),
            sample_rate=16000,
            timestamp_ms=200,
        ))

        time.sleep(0.4)

        # Both should have independent silence events
        ids_with_events = {e.exchange_id for e in events if e.reason == SilenceReason.THRESHOLD_REACHED}
        assert 1 in ids_with_events
        assert 2 in ids_with_events

        svc.stop_session(1)
        svc.stop_session(2)

    def test_stop_one_session_doesnt_affect_other(self):
        svc = AudioIngestionService()

        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.start_session(exchange_id=2, sample_rate=16000)

        svc.stop_session(1)

        # Session 2 should still work
        chunk = svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=2,
            audio_chunk=_pcm(),
            sample_rate=16000,
            timestamp_ms=0,
        ))
        assert chunk.exchange_id == 2

        svc.stop_session(2)

    def test_pause_one_session_doesnt_affect_other(self):
        svc = AudioIngestionService()

        svc.start_session(exchange_id=1, sample_rate=16000)
        svc.start_session(exchange_id=2, sample_rate=16000)

        svc.pause_session(1)

        # Session 2 still accepts audio
        chunk = svc.ingest_chunk(AudioStreamRequest(
            interview_exchange_id=2,
            audio_chunk=_pcm(),
            sample_rate=16000,
            timestamp_ms=0,
        ))
        assert chunk.exchange_id == 2

        svc.stop_session(1)
        svc.stop_session(2)
