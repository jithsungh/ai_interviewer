"""
Unit tests for SilenceDetector.

Covers:
- Timer starts after audio chunk
- Timer resets on new audio
- Event emission after threshold
- Race condition: new audio cancels timer
- Thread safety with concurrent chunks
- Configurable threshold
- Session close reason
"""

import pytest
import time
import threading
from unittest.mock import Mock

from app.audio.ingestion.silence_detector import SilenceDetector
from app.audio.ingestion.contracts import SilenceReason


class TestSilenceTimerLifecycle:

    def test_timer_starts_after_audio(self):
        detector = SilenceDetector(threshold_ms=3000, exchange_id=1)
        detector.on_audio_chunk(timestamp_ms=1000)

        assert detector.timer is not None
        assert detector.timer.is_alive()

        detector.cancel()

    def test_timer_resets_on_new_audio(self):
        detector = SilenceDetector(threshold_ms=3000, exchange_id=1)

        detector.on_audio_chunk(timestamp_ms=1000)
        first_timer = detector.timer

        time.sleep(0.05)

        detector.on_audio_chunk(timestamp_ms=2000)
        second_timer = detector.timer

        assert first_timer is not second_timer
        # cancel() sets the Timer's internal event but the thread may not
        # have exited yet — join to avoid a scheduling-dependent flake.
        first_timer.join(timeout=1.0)
        assert not first_timer.is_alive()
        assert second_timer.is_alive()

        detector.cancel()

    def test_no_timer_before_first_chunk(self):
        detector = SilenceDetector(threshold_ms=3000)
        assert detector.timer is None


class TestSilenceEventEmission:

    def test_event_emitted_after_threshold(self):
        detector = SilenceDetector(threshold_ms=200, exchange_id=42)

        events = []
        detector.on_silence_detected(lambda e: events.append(e))

        detector.on_audio_chunk(timestamp_ms=1000)
        time.sleep(0.4)

        assert len(events) == 1
        assert events[0].exchange_id == 42
        assert events[0].silence_duration_ms >= 200
        assert events[0].reason == SilenceReason.THRESHOLD_REACHED
        assert events[0].should_evaluate is True

    def test_no_event_before_threshold(self):
        detector = SilenceDetector(threshold_ms=1000, exchange_id=1)

        events = []
        detector.on_silence_detected(lambda e: events.append(e))

        detector.on_audio_chunk(timestamp_ms=1000)
        time.sleep(0.2)

        assert len(events) == 0
        detector.cancel()


class TestRaceCondition:

    def test_new_audio_cancels_timer(self):
        """New audio arriving just before timer fires prevents evaluation."""
        detector = SilenceDetector(threshold_ms=300, exchange_id=1)

        events = []
        detector.on_silence_detected(lambda e: events.append(e))

        detector.on_audio_chunk(timestamp_ms=1000)
        time.sleep(0.2)  # 200ms — not yet at 300ms threshold

        # New audio arrives
        detector.on_audio_chunk(timestamp_ms=1200)
        time.sleep(0.15)  # Only 150ms since last chunk

        assert len(events) == 0
        detector.cancel()

    def test_evaluation_triggered_flag(self):
        detector = SilenceDetector(threshold_ms=200, exchange_id=1)

        detector.on_audio_chunk(timestamp_ms=1000)

        assert detector.evaluation_triggered is False

        time.sleep(0.4)

        assert detector.evaluation_triggered is True


class TestThreadSafety:

    def test_concurrent_chunks_no_crash(self):
        detector = SilenceDetector(threshold_ms=300, exchange_id=1)

        events = []
        detector.on_silence_detected(lambda e: events.append(e))

        def send_chunk(ts):
            detector.on_audio_chunk(timestamp_ms=ts)

        threads = [
            threading.Thread(target=send_chunk, args=(i * 10,))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(0.5)

        # Exactly one event after silence
        assert len(events) == 1
        detector.cancel()


class TestConfigurableThreshold:

    def test_different_thresholds(self):
        d3 = SilenceDetector(threshold_ms=3000)
        d5 = SilenceDetector(threshold_ms=5000)

        assert d3.threshold_ms == 3000
        assert d5.threshold_ms == 5000


class TestCloseSession:

    def test_close_emits_session_ended(self):
        detector = SilenceDetector(threshold_ms=3000, exchange_id=99)

        events = []
        detector.on_silence_detected(lambda e: events.append(e))

        detector.on_audio_chunk(timestamp_ms=1000)
        detector.close_session()

        assert len(events) == 1
        assert events[0].reason == SilenceReason.SESSION_ENDED
        assert events[0].exchange_id == 99

    def test_close_is_idempotent(self):
        detector = SilenceDetector(threshold_ms=3000, exchange_id=1)

        events = []
        detector.on_silence_detected(lambda e: events.append(e))

        detector.close_session()
        detector.close_session()

        assert len(events) == 1


class TestIsSilent:

    def test_not_silent_immediately(self):
        detector = SilenceDetector(threshold_ms=200)
        detector.on_audio_chunk(timestamp_ms=1000)
        assert detector.is_silent() is False

    def test_silent_after_threshold(self):
        detector = SilenceDetector(threshold_ms=100)
        detector.on_audio_chunk(timestamp_ms=1000)
        time.sleep(0.2)
        assert detector.is_silent() is True

    def test_not_silent_without_any_audio(self):
        detector = SilenceDetector(threshold_ms=100)
        assert detector.is_silent() is False
