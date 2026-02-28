"""
Audio Ingestion Service

Orchestrates the ingestion pipeline:
  1. Validate session / exchange context
  2. Normalise audio (resample, mono, volume)
  3. Buffer normalised chunks
  4. Feed silence detector
  5. Forward buffered windows to transcription (via callback)

This is the **single public entry point** consumed by the API layer
and by integration tests.

Invariants enforced:
- One active session per exchange
- Session must be active (not paused, not closed)
- All audio forwarded to transcription is 16 kHz mono

Does NOT:
- Write to any database table
- Advance interview state
- Trigger evaluations directly
"""

from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional

import numpy as np

from app.shared.observability import get_context_logger

from .buffer_manager import AudioBufferManager, AudioWindow
from .contracts import (
    AudioChunk,
    AudioSessionControl,
    AudioStreamRequest,
    SessionAction,
    SilenceDetectedEvent,
)
from .exceptions import (
    SessionClosedError,
    SessionNotFoundError,
    SessionPausedError,
)
from .normalizer import AudioNormalizer
from .session_manager import AudioSession, AudioSessionManager

logger = get_context_logger(__name__)

# Type alias for downstream consumer
TranscriptionCallback = Callable[[List[AudioWindow]], None]


class AudioIngestionService:
    """
    Facade for the audio ingestion pipeline.

    Parameters
    ----------
    silence_threshold_ms : int
        Silence detection threshold forwarded to each session's detector.
    buffer_window_ms : int
        Width of the buffering window in milliseconds.
    max_buffer_duration_s : int
        Maximum buffered audio before eviction (seconds).
    session_timeout_s : int
        Auto-close a session after this many seconds of inactivity.
    """

    def __init__(
        self,
        silence_threshold_ms: int = 3000,
        buffer_window_ms: int = 500,
        max_buffer_duration_s: int = 30,
        session_timeout_s: int = 10,
    ):
        self._normalizer = AudioNormalizer()
        self._session_manager = AudioSessionManager(
            default_silence_threshold_ms=silence_threshold_ms,
            timeout_s=session_timeout_s,
        )
        self._buffer_window_ms = buffer_window_ms
        self._max_buffer_duration_s = max_buffer_duration_s

        # Per-exchange buffers
        self._buffers: dict[int, AudioBufferManager] = {}

        # Callbacks
        self._silence_callbacks: List[Callable[[SilenceDetectedEvent], None]] = []
        self._transcription_callback: Optional[TranscriptionCallback] = None

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_silence_detected(
        self, callback: Callable[[SilenceDetectedEvent], None]
    ) -> None:
        """Register a callback for silence events (forwarded to orchestrator)."""
        self._silence_callbacks.append(callback)
        self._session_manager.on_silence_detected(callback)

    def on_transcription_ready(self, callback: TranscriptionCallback) -> None:
        """Register a callback invoked when a full buffer window is ready."""
        self._transcription_callback = callback

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(
        self,
        exchange_id: int,
        sample_rate: int,
        silence_threshold_ms: Optional[int] = None,
    ) -> AudioSession:
        """
        Start a new audio session bound to *exchange_id*.

        Raises SessionAlreadyActiveError if session exists.
        """
        session = self._session_manager.start_session(
            exchange_id=exchange_id,
            sample_rate=sample_rate,
            silence_threshold_ms=silence_threshold_ms,
        )

        self._buffers[exchange_id] = AudioBufferManager(
            window_ms=self._buffer_window_ms,
            max_duration_s=self._max_buffer_duration_s,
        )

        logger.info(
            "Audio session started",
            event_type="audio.session.started",
            metadata={"exchange_id": exchange_id, "sample_rate": sample_rate},
        )
        return session

    def pause_session(self, exchange_id: int, reason: Optional[str] = None) -> None:
        self._session_manager.pause_session(exchange_id, reason)
        logger.info(
            "Audio session paused",
            event_type="audio.session.paused",
            metadata={"exchange_id": exchange_id, "reason": reason},
        )

    def resume_session(self, exchange_id: int) -> None:
        self._session_manager.resume_session(exchange_id)
        logger.info(
            "Audio session resumed",
            event_type="audio.session.resumed",
            metadata={"exchange_id": exchange_id},
        )

    def stop_session(self, exchange_id: int) -> None:
        # Flush remaining buffer
        buf = self._buffers.pop(exchange_id, None)
        if buf is not None:
            windows = buf.flush()
            if windows and self._transcription_callback:
                try:
                    self._transcription_callback(windows)
                except Exception:
                    logger.warning(
                        "Transcription callback failed during session stop",
                        event_type="audio.transcription.callback_error",
                        metadata={"exchange_id": exchange_id},
                    )

        self._session_manager.stop_session(exchange_id)
        logger.info(
            "Audio session stopped",
            event_type="audio.session.stopped",
            metadata={"exchange_id": exchange_id},
        )

    def finalize_session(self, exchange_id: int) -> None:
        """Alias for stop_session used by integration code."""
        self.stop_session(exchange_id)

    # ------------------------------------------------------------------
    # Audio ingestion
    # ------------------------------------------------------------------

    def ingest_chunk(self, request: AudioStreamRequest) -> AudioChunk:
        """
        Process a single audio chunk.

        1. Validate session state
        2. Normalise audio
        3. Buffer normalised data
        4. Update silence detector
        5. Optionally forward to transcription

        Returns the normalised AudioChunk.
        """
        eid = request.interview_exchange_id

        # Validate session
        session = self._session_manager.get_session(eid)
        if not session.is_active:
            raise SessionClosedError(eid)
        if session.is_paused:
            raise SessionPausedError(eid)

        # Decode raw bytes to float32 ndarray
        raw_audio = np.frombuffer(request.audio_chunk, dtype=np.float32).copy()

        # Normalise
        normalized = self._normalizer.normalize(
            raw_audio,
            source_rate=request.sample_rate,
            source_channels=request.channels,
        )

        duration_ms = self._normalizer.compute_duration_ms(
            len(normalized), self._normalizer.output_sample_rate
        )

        timestamp_ms = request.timestamp_ms or int(time.monotonic() * 1000)

        chunk = AudioChunk(
            exchange_id=eid,
            audio_data=normalized.tobytes(),
            sample_rate=self._normalizer.output_sample_rate,
            channels=self._normalizer.output_channels,
            timestamp_ms=timestamp_ms,
            duration_ms=duration_ms,
            normalized=True,
        )

        # Buffer
        buf = self._buffers.get(eid)
        if buf is not None:
            buf.add_chunk(normalized, timestamp_ms)

        # Feed silence detector
        session.touch()
        session.chunk_count += 1
        if session.silence_detector is not None:
            session.silence_detector.on_audio_chunk(timestamp_ms)

        # Forward windows if a full buffer is ready
        if buf is not None and self._transcription_callback:
            windows = buf.get_windows()
            if len(windows) >= 2:
                # Forward all complete windows except the last (still accumulating)
                ready = buf.flush()
                if ready:
                    try:
                        self._transcription_callback(ready)
                    except Exception:
                        logger.warning(
                            "Transcription callback failed",
                            event_type="audio.transcription.callback_error",
                            metadata={"exchange_id": eid},
                        )

        return chunk

    # ------------------------------------------------------------------
    # Session control dispatch
    # ------------------------------------------------------------------

    def handle_session_control(self, control: AudioSessionControl) -> None:
        """
        Dispatch a session control command.

        Thin dispatcher — delegates to the appropriate lifecycle method.
        """
        eid = control.interview_exchange_id

        if control.action == SessionAction.START:
            self.start_session(exchange_id=eid, sample_rate=16000)
        elif control.action == SessionAction.PAUSE:
            self.pause_session(exchange_id=eid, reason=control.reason)
        elif control.action == SessionAction.RESUME:
            self.resume_session(exchange_id=eid)
        elif control.action == SessionAction.STOP:
            self.stop_session(exchange_id=eid)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def cleanup_timed_out_sessions(self) -> List[int]:
        """Remove sessions that have exceeded the inactivity timeout."""
        expired = self._session_manager.cleanup_timed_out()
        for eid in expired:
            self._buffers.pop(eid, None)
        return expired
