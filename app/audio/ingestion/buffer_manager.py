"""
Audio Buffer Manager

Accumulates audio chunks into time-windowed buffers that are forwarded to
the transcription module.

Pure domain logic — no I/O, no database, no FastAPI.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class BufferedChunk:
    """Single timestamped audio chunk in the buffer."""
    audio_data: np.ndarray
    timestamp_ms: int


@dataclass
class AudioWindow:
    """
    Time-windowed aggregate of buffered audio chunks.

    ``chunks`` are guaranteed to be sorted by ``timestamp_ms``.
    """
    chunks: List[BufferedChunk] = field(default_factory=list)
    start_ms: int = 0
    end_ms: int = 0

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


class AudioBufferManager:
    """
    Buffers audio chunks and assembles them into fixed-duration windows.

    Parameters
    ----------
    window_ms : int
        Duration of each output window in milliseconds.
    max_duration_s : int
        Maximum total buffer duration (seconds). Older data is evicted.
    """

    def __init__(self, window_ms: int = 500, max_duration_s: int = 30):
        self._window_ms = window_ms
        self._max_duration_ms = max_duration_s * 1000
        self._chunks: List[BufferedChunk] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_chunk(
        self,
        audio_data: np.ndarray | bytes,
        timestamp_ms: int,
    ) -> None:
        """
        Append a chunk to the internal buffer.

        Chunks are kept sorted by ``timestamp_ms`` to handle out-of-order delivery.
        Oldest data beyond ``max_duration_s`` is evicted.
        """
        if isinstance(audio_data, bytes):
            audio_data = np.frombuffer(audio_data, dtype=np.float32)

        chunk = BufferedChunk(audio_data=audio_data, timestamp_ms=timestamp_ms)

        with self._lock:
            self._chunks.append(chunk)
            self._chunks.sort(key=lambda c: c.timestamp_ms)
            self._evict()

    def get_windows(self) -> List[AudioWindow]:
        """
        Partition the current buffer into non-overlapping windows of
        ``window_ms`` duration.

        Does NOT drain the buffer — call ``flush()`` for that.
        """
        with self._lock:
            return self._build_windows(self._chunks)

    def flush(self) -> List[AudioWindow]:
        """
        Return all buffered windows and clear the internal buffer.
        """
        with self._lock:
            windows = self._build_windows(self._chunks)
            self._chunks.clear()
        return windows

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._chunks) == 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict(self) -> None:
        """Drop oldest chunks until total duration ≤ max_duration_ms."""
        if not self._chunks or self._max_duration_ms <= 0:
            return
        latest = self._chunks[-1].timestamp_ms
        cutoff = latest - self._max_duration_ms
        self._chunks = [c for c in self._chunks if c.timestamp_ms >= cutoff]

    def _build_windows(self, chunks: List[BufferedChunk]) -> List[AudioWindow]:
        if not chunks:
            return []

        windows: List[AudioWindow] = []
        first_ts = chunks[0].timestamp_ms
        current_window = AudioWindow(start_ms=first_ts, end_ms=first_ts + self._window_ms)

        for chunk in chunks:
            if chunk.timestamp_ms < current_window.end_ms:
                current_window.chunks.append(chunk)
            else:
                if current_window.chunks:
                    windows.append(current_window)
                window_start = chunk.timestamp_ms
                current_window = AudioWindow(
                    start_ms=window_start,
                    end_ms=window_start + self._window_ms,
                    chunks=[chunk],
                )

        if current_window.chunks:
            windows.append(current_window)

        return windows
