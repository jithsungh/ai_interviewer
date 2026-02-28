"""
Silence Detector

Thread-safe silence detection with configurable threshold.

Critical invariant: silence timer expiration MUST atomically verify that
no new audio has arrived since the timer was started.  This prevents
spurious evaluation triggers caused by race conditions between the
silence callback and incoming audio chunks.

Pure domain logic — no I/O, no database access, no FastAPI imports.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from .contracts import SilenceDetectedEvent, SilenceReason


class SilenceDetector:
    """
    Per-session silence detector.

    Parameters
    ----------
    threshold_ms : int
        Silence duration (in ms) before emitting a SilenceDetectedEvent.
    exchange_id : int
        The exchange this detector is bound to.
    """

    def __init__(self, threshold_ms: int = 3000, exchange_id: int = 0):
        self.threshold_ms = threshold_ms
        self.exchange_id = exchange_id

        # Protected by _lock
        self._lock = threading.Lock()
        self._last_audio_timestamp_ms: Optional[int] = None
        self._last_audio_wall_time: Optional[float] = None  # monotonic seconds
        self._timer: Optional[threading.Timer] = None
        self._callbacks: List[Callable[[SilenceDetectedEvent], None]] = []
        self._closed = False
        self._evaluation_triggered = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def timer(self) -> Optional[threading.Timer]:
        with self._lock:
            return self._timer

    @property
    def evaluation_triggered(self) -> bool:
        with self._lock:
            return self._evaluation_triggered

    def on_silence_detected(self, callback: Callable[[SilenceDetectedEvent], None]) -> None:
        """Register a callback invoked when silence threshold is reached."""
        with self._lock:
            self._callbacks.append(callback)

    def on_audio_chunk(self, timestamp_ms: int) -> None:
        """
        Notify the detector that a new audio chunk has arrived.

        Atomically cancels any pending timer and starts a fresh one.
        """
        with self._lock:
            if self._closed:
                return

            # Cancel existing timer
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            self._last_audio_timestamp_ms = timestamp_ms
            self._last_audio_wall_time = time.monotonic()
            self._evaluation_triggered = False

            # Start new timer
            delay_s = self.threshold_ms / 1000.0
            self._timer = threading.Timer(delay_s, self._check_silence)
            self._timer.daemon = True
            self._timer.start()

    def start_silence_timer(self) -> None:
        """
        Explicitly (re)start the silence timer.

        Used in tests to inject a timer without sending a real chunk.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            delay_s = self.threshold_ms / 1000.0
            self._timer = threading.Timer(delay_s, self._check_silence)
            self._timer.daemon = True
            self._timer.start()

    def is_silent(self) -> bool:
        """
        Return ``True`` if enough wall-clock time has elapsed since
        the last audio chunk to exceed the silence threshold.
        """
        with self._lock:
            if self._last_audio_wall_time is None:
                return False
            elapsed_ms = (time.monotonic() - self._last_audio_wall_time) * 1000.0
            return elapsed_ms >= self.threshold_ms

    def close_session(self) -> None:
        """
        Mark the detector as closed and emit a ``session_ended`` event.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            event = SilenceDetectedEvent(
                exchange_id=self.exchange_id,
                silence_duration_ms=0,
                last_audio_timestamp_ms=self._last_audio_timestamp_ms or 0,
                should_evaluate=True,
                reason=SilenceReason.SESSION_ENDED,
            )

        # Invoke callbacks outside the lock to avoid deadlock
        self._fire_callbacks(event)

    def cancel(self) -> None:
        """Cancel any pending timer without emitting events."""
        with self._lock:
            self._closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_silence(self) -> None:
        """
        Timer callback.  Atomically verify that no new audio has arrived
        since the timer was started.
        """
        with self._lock:
            if self._closed:
                return
            if self._last_audio_wall_time is None:
                return

            elapsed_ms = (time.monotonic() - self._last_audio_wall_time) * 1000.0
            if elapsed_ms < self.threshold_ms:
                # New audio arrived after the timer started — false alarm.
                return

            self._evaluation_triggered = True
            event = SilenceDetectedEvent(
                exchange_id=self.exchange_id,
                silence_duration_ms=int(elapsed_ms),
                last_audio_timestamp_ms=self._last_audio_timestamp_ms or 0,
                should_evaluate=True,
                reason=SilenceReason.THRESHOLD_REACHED,
            )

        # Fire outside lock
        self._fire_callbacks(event)

    def _fire_callbacks(self, event: SilenceDetectedEvent) -> None:
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                pass  # Callback errors must not crash the detector
