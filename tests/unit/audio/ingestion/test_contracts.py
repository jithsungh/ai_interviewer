"""
Unit tests for audio ingestion contracts (dataclass validation).

Covers input validation, immutability, and edge cases.
"""

import pytest

from app.audio.ingestion.contracts import (
    AudioChunk,
    AudioSessionControl,
    AudioStreamRequest,
    SessionAction,
    SilenceDetectedEvent,
    SilenceReason,
)


class TestAudioStreamRequest:

    def test_valid_construction(self):
        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=b"\x01\x02",
            sample_rate=16000,
        )
        assert req.interview_exchange_id == 1
        assert req.channels == 1  # default

    def test_invalid_exchange_id(self):
        with pytest.raises(ValueError, match="positive"):
            AudioStreamRequest(
                interview_exchange_id=0,
                audio_chunk=b"\x01",
                sample_rate=16000,
            )

    def test_empty_audio_chunk(self):
        with pytest.raises(ValueError, match="empty"):
            AudioStreamRequest(
                interview_exchange_id=1,
                audio_chunk=b"",
                sample_rate=16000,
            )

    def test_invalid_sample_rate(self):
        with pytest.raises(ValueError, match="positive"):
            AudioStreamRequest(
                interview_exchange_id=1,
                audio_chunk=b"\x01",
                sample_rate=-1,
            )

    def test_invalid_channels(self):
        with pytest.raises(ValueError, match="channels"):
            AudioStreamRequest(
                interview_exchange_id=1,
                audio_chunk=b"\x01",
                sample_rate=16000,
                channels=0,
            )

    def test_immutable(self):
        req = AudioStreamRequest(
            interview_exchange_id=1,
            audio_chunk=b"\x01",
            sample_rate=16000,
        )
        with pytest.raises(AttributeError):
            req.sample_rate = 8000  # type: ignore


class TestAudioSessionControl:

    def test_valid_pause(self):
        ctrl = AudioSessionControl(
            interview_exchange_id=5,
            action=SessionAction.PAUSE,
            reason="user paused",
        )
        assert ctrl.action == SessionAction.PAUSE

    def test_invalid_exchange_id(self):
        with pytest.raises(ValueError, match="positive"):
            AudioSessionControl(
                interview_exchange_id=-1,
                action=SessionAction.START,
            )


class TestAudioChunk:

    def test_construction(self):
        chunk = AudioChunk(
            exchange_id=1,
            audio_data=b"\x00",
            sample_rate=16000,
            channels=1,
            timestamp_ms=500,
            duration_ms=100,
            normalized=True,
        )
        assert chunk.normalized is True
        assert chunk.duration_ms == 100


class TestSilenceDetectedEvent:

    def test_construction(self):
        event = SilenceDetectedEvent(
            exchange_id=1,
            silence_duration_ms=3200,
            last_audio_timestamp_ms=1000,
            should_evaluate=True,
            reason=SilenceReason.THRESHOLD_REACHED,
        )
        assert event.should_evaluate is True
        assert event.reason == SilenceReason.THRESHOLD_REACHED

    def test_session_ended_reason(self):
        event = SilenceDetectedEvent(
            exchange_id=2,
            silence_duration_ms=0,
            last_audio_timestamp_ms=0,
            should_evaluate=True,
            reason=SilenceReason.SESSION_ENDED,
        )
        assert event.reason == SilenceReason.SESSION_ENDED


class TestEnums:

    def test_session_action_values(self):
        assert SessionAction.START.value == "start"
        assert SessionAction.PAUSE.value == "pause"
        assert SessionAction.RESUME.value == "resume"
        assert SessionAction.STOP.value == "stop"

    def test_silence_reason_values(self):
        assert SilenceReason.THRESHOLD_REACHED.value == "threshold_reached"
        assert SilenceReason.SESSION_ENDED.value == "session_ended"
