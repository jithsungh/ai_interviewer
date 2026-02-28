"""
Unit tests for AudioSessionManager.

Covers:
- Start / get / pause / resume / stop lifecycle
- Duplicate session prevention
- Session isolation across exchanges
- Timeout-based cleanup
"""

import pytest
import time

from app.audio.ingestion.session_manager import AudioSessionManager
from app.audio.ingestion.exceptions import (
    SessionAlreadyActiveError,
    SessionNotFoundError,
)
from app.audio.ingestion.contracts import SilenceReason


class TestStartSession:

    def test_start_new_session(self):
        mgr = AudioSessionManager()
        session = mgr.start_session(exchange_id=123, sample_rate=16000)

        assert session.exchange_id == 123
        assert session.is_active is True
        assert session.is_paused is False
        assert session.silence_detector is not None

        mgr.stop_session(123)

    def test_cannot_start_duplicate_session(self):
        mgr = AudioSessionManager()
        mgr.start_session(exchange_id=123, sample_rate=16000)

        with pytest.raises(SessionAlreadyActiveError):
            mgr.start_session(exchange_id=123, sample_rate=16000)

        mgr.stop_session(123)

    def test_can_start_after_stop(self):
        mgr = AudioSessionManager()
        mgr.start_session(exchange_id=123, sample_rate=16000)
        mgr.stop_session(123)
        session = mgr.start_session(exchange_id=123, sample_rate=16000)
        assert session.is_active is True
        mgr.stop_session(123)


class TestGetSession:

    def test_get_existing_session(self):
        mgr = AudioSessionManager()
        mgr.start_session(exchange_id=10, sample_rate=16000)

        session = mgr.get_session(10)
        assert session.exchange_id == 10

        mgr.stop_session(10)

    def test_get_nonexistent_raises(self):
        mgr = AudioSessionManager()
        with pytest.raises(SessionNotFoundError):
            mgr.get_session(999)


class TestPauseResume:

    def test_pause_and_resume(self):
        mgr = AudioSessionManager()
        session = mgr.start_session(exchange_id=1, sample_rate=16000)

        mgr.pause_session(1, reason="user paused")
        assert session.is_paused is True

        mgr.resume_session(1)
        assert session.is_paused is False

        mgr.stop_session(1)

    def test_pause_nonexistent_raises(self):
        mgr = AudioSessionManager()
        with pytest.raises(SessionNotFoundError):
            mgr.pause_session(999)


class TestStopSession:

    def test_stop_removes_session(self):
        mgr = AudioSessionManager()
        mgr.start_session(exchange_id=1, sample_rate=16000)
        mgr.stop_session(1)

        with pytest.raises(SessionNotFoundError):
            mgr.get_session(1)

    def test_stop_nonexistent_raises(self):
        mgr = AudioSessionManager()
        with pytest.raises(SessionNotFoundError):
            mgr.stop_session(999)

    def test_stop_emits_silence_event(self):
        mgr = AudioSessionManager()
        events = []
        mgr.on_silence_detected(lambda e: events.append(e))

        mgr.start_session(exchange_id=55, sample_rate=16000)
        mgr.stop_session(55)

        assert len(events) == 1
        assert events[0].reason == SilenceReason.SESSION_ENDED
        assert events[0].exchange_id == 55


class TestIsolation:

    def test_concurrent_sessions_isolated(self):
        mgr = AudioSessionManager()
        s1 = mgr.start_session(exchange_id=100, sample_rate=16000)
        s2 = mgr.start_session(exchange_id=200, sample_rate=16000)

        assert s1.exchange_id != s2.exchange_id

        mgr.pause_session(100)
        assert s1.is_paused is True
        assert s2.is_paused is False

        mgr.stop_session(100)
        mgr.stop_session(200)


class TestHasSession:

    def test_has_session(self):
        mgr = AudioSessionManager()
        assert mgr.has_session(1) is False

        mgr.start_session(exchange_id=1, sample_rate=16000)
        assert mgr.has_session(1) is True

        mgr.stop_session(1)
        assert mgr.has_session(1) is False


class TestActiveCount:

    def test_active_count(self):
        mgr = AudioSessionManager()
        assert mgr.active_session_count() == 0

        mgr.start_session(exchange_id=1, sample_rate=16000)
        mgr.start_session(exchange_id=2, sample_rate=16000)
        assert mgr.active_session_count() == 2

        mgr.stop_session(1)
        assert mgr.active_session_count() == 1

        mgr.stop_session(2)


class TestTimeoutCleanup:

    def test_cleanup_expired_sessions(self):
        mgr = AudioSessionManager(timeout_s=1)

        s = mgr.start_session(exchange_id=1, sample_rate=16000)
        # Manually backdate
        s.last_activity_at = time.monotonic() - 2

        expired = mgr.cleanup_timed_out()
        assert 1 in expired
        assert mgr.has_session(1) is False

    def test_cleanup_skips_active_sessions(self):
        mgr = AudioSessionManager(timeout_s=10)

        mgr.start_session(exchange_id=1, sample_rate=16000)
        expired = mgr.cleanup_timed_out()
        assert len(expired) == 0

        mgr.stop_session(1)

    def test_cleanup_disabled_when_zero(self):
        mgr = AudioSessionManager(timeout_s=0)
        s = mgr.start_session(exchange_id=1, sample_rate=16000)
        s.last_activity_at = time.monotonic() - 1000

        expired = mgr.cleanup_timed_out()
        assert len(expired) == 0

        mgr.stop_session(1)
