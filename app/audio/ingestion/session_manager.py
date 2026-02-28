"""
Audio Session Manager

Thread-safe registry of active audio sessions.
Enforces the invariant: **one active session per exchange**.

Pure domain logic — no I/O, no database, no FastAPI.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .contracts import AudioChunk, SilenceDetectedEvent, SilenceReason
from .exceptions import (
    SessionAlreadyActiveError,
    SessionClosedError,
    SessionNotFoundError,
    SessionPausedError,
)
from .silence_detector import SilenceDetector


@dataclass
class AudioSession:
    """
    In-memory representation of a single audio streaming session.

    One session is bound to exactly one ``interview_exchange_id``.
    """

    exchange_id: int
    sample_rate: int
    is_active: bool = True
    is_paused: bool = False
    created_at: float = field(default_factory=time.monotonic)
    last_activity_at: float = field(default_factory=time.monotonic)
    chunk_count: int = 0
    silence_detector: Optional[SilenceDetector] = None

    def touch(self) -> None:
        self.last_activity_at = time.monotonic()


class AudioSessionManager:
    """
    Manages lifecycle of audio sessions with thread-safe access.

    Parameters
    ----------
    default_silence_threshold_ms : int
        Default silence threshold passed to each session's SilenceDetector.
    timeout_s : int
        Inactivity timeout (seconds) after which a session is auto-closed.
        Use ``0`` to disable.
    """

    def __init__(
        self,
        default_silence_threshold_ms: int = 3000,
        timeout_s: int = 10,
    ):
        self._sessions: Dict[int, AudioSession] = {}
        self._lock = threading.Lock()
        self._default_silence_threshold_ms = default_silence_threshold_ms
        self._timeout_s = timeout_s
        self._silence_callbacks: List[Callable[[SilenceDetectedEvent], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_silence_detected(self, callback: Callable[[SilenceDetectedEvent], None]) -> None:
        """Register a global silence callback applied to every new session."""
        self._silence_callbacks.append(callback)

    def start_session(
        self,
        exchange_id: int,
        sample_rate: int,
        silence_threshold_ms: Optional[int] = None,
    ) -> AudioSession:
        """
        Create and register a new audio session.

        Raises
        ------
        SessionAlreadyActiveError
            If a session for the given exchange already exists.
        """
        threshold = silence_threshold_ms or self._default_silence_threshold_ms

        with self._lock:
            if exchange_id in self._sessions:
                raise SessionAlreadyActiveError(exchange_id)

            detector = SilenceDetector(
                threshold_ms=threshold,
                exchange_id=exchange_id,
            )
            for cb in self._silence_callbacks:
                detector.on_silence_detected(cb)

            session = AudioSession(
                exchange_id=exchange_id,
                sample_rate=sample_rate,
                silence_detector=detector,
            )
            self._sessions[exchange_id] = session

        return session

    def get_session(self, exchange_id: int) -> AudioSession:
        """
        Retrieve an active session.

        Raises
        ------
        SessionNotFoundError
            If no session exists for this exchange.
        """
        with self._lock:
            session = self._sessions.get(exchange_id)
        if session is None:
            raise SessionNotFoundError(exchange_id)
        return session

    def pause_session(self, exchange_id: int, reason: Optional[str] = None) -> None:
        """
        Pause an active session.

        While paused the silence timer is cancelled and new audio
        chunks are rejected.
        """
        session = self.get_session(exchange_id)
        with self._lock:
            session.is_paused = True
            if session.silence_detector is not None:
                session.silence_detector.cancel()

    def resume_session(self, exchange_id: int) -> None:
        """Resume a paused session."""
        session = self.get_session(exchange_id)
        with self._lock:
            session.is_paused = False
            # Re-create the silence detector since cancel() marks it closed
            old = session.silence_detector
            if old is not None:
                new_detector = SilenceDetector(
                    threshold_ms=old.threshold_ms,
                    exchange_id=exchange_id,
                )
                for cb in self._silence_callbacks:
                    new_detector.on_silence_detected(cb)
                session.silence_detector = new_detector

    def stop_session(self, exchange_id: int) -> None:
        """
        Stop and remove a session.

        Emits a ``SilenceDetectedEvent`` with reason ``session_ended``.
        """
        with self._lock:
            session = self._sessions.pop(exchange_id, None)
        if session is None:
            raise SessionNotFoundError(exchange_id)
        session.is_active = False
        if session.silence_detector is not None:
            session.silence_detector.close_session()

    def has_session(self, exchange_id: int) -> bool:
        with self._lock:
            return exchange_id in self._sessions

    def active_session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def cleanup_timed_out(self) -> List[int]:
        """
        Remove sessions that have exceeded the inactivity timeout.

        Returns list of exchange_ids that were closed.
        """
        if self._timeout_s <= 0:
            return []

        now = time.monotonic()
        expired: List[int] = []

        with self._lock:
            for eid, session in list(self._sessions.items()):
                if now - session.last_activity_at > self._timeout_s:
                    expired.append(eid)
                    del self._sessions[eid]

        # Fire close events outside lock
        for eid in expired:
            # Session already removed; fire a synthetic session_ended event
            event = SilenceDetectedEvent(
                exchange_id=eid,
                silence_duration_ms=self._timeout_s * 1000,
                last_audio_timestamp_ms=0,
                should_evaluate=True,
                reason=SilenceReason.SESSION_ENDED,
            )
            for cb in self._silence_callbacks:
                try:
                    cb(event)
                except Exception:
                    pass

        return expired
