"""
Unit tests for AudioBufferManager.

Covers:
- Chunk buffering and windowing
- Flush clears buffer
- Max duration eviction
- Out-of-order chunk reordering
"""

import pytest
import numpy as np

from app.audio.ingestion.buffer_manager import AudioBufferManager


class TestAddAndWindow:

    def test_buffer_chunks_by_time_window(self):
        mgr = AudioBufferManager(window_ms=500)

        for i in range(10):
            mgr.add_chunk(
                audio_data=np.random.randn(1600).astype(np.float32),
                timestamp_ms=i * 100,
            )

        windows = mgr.get_windows()
        assert len(windows) == 2  # 0-499 and 500-999

    def test_single_chunk_single_window(self):
        mgr = AudioBufferManager(window_ms=500)
        mgr.add_chunk(np.zeros(1600, dtype=np.float32), timestamp_ms=0)

        windows = mgr.get_windows()
        assert len(windows) == 1
        assert len(windows[0].chunks) == 1


class TestFlush:

    def test_flush_clears_buffer(self):
        mgr = AudioBufferManager(window_ms=500)
        mgr.add_chunk(np.random.randn(8000).astype(np.float32), timestamp_ms=0)

        flushed = mgr.flush()
        assert len(flushed) > 0
        assert mgr.is_empty()

    def test_flush_empty_buffer(self):
        mgr = AudioBufferManager(window_ms=500)
        assert mgr.flush() == []


class TestMaxDuration:

    def test_evicts_old_chunks(self):
        mgr = AudioBufferManager(window_ms=500, max_duration_s=2)

        # Add 3 seconds of audio at 100ms intervals
        for i in range(30):
            mgr.add_chunk(
                audio_data=np.random.randn(1600).astype(np.float32),
                timestamp_ms=i * 100,
            )

        windows = mgr.get_windows()
        total_duration_ms = sum(w.duration_ms for w in windows)
        assert total_duration_ms <= 2500  # 2s + one window tolerance


class TestOrdering:

    def test_chunks_ordered_by_timestamp(self):
        mgr = AudioBufferManager(window_ms=500)

        mgr.add_chunk(audio_data=np.zeros(10, dtype=np.float32), timestamp_ms=300)
        mgr.add_chunk(audio_data=np.zeros(10, dtype=np.float32), timestamp_ms=100)
        mgr.add_chunk(audio_data=np.zeros(10, dtype=np.float32), timestamp_ms=200)

        windows = mgr.get_windows()
        chunks = windows[0].chunks

        timestamps = [c.timestamp_ms for c in chunks]
        assert timestamps == sorted(timestamps)


class TestIsEmpty:

    def test_empty_initially(self):
        mgr = AudioBufferManager(window_ms=500)
        assert mgr.is_empty() is True

    def test_not_empty_after_add(self):
        mgr = AudioBufferManager(window_ms=500)
        mgr.add_chunk(np.zeros(10, dtype=np.float32), timestamp_ms=0)
        assert mgr.is_empty() is False
