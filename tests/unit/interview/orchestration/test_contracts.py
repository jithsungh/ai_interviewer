"""
Unit Tests — Orchestration Contracts

Tests Pydantic validation for all orchestration DTOs.
Pure validation — no I/O, no mocks.
"""

import pytest

from app.interview.orchestration.contracts import (
    AudioCompletionSignal,
    CodeCompletionSignal,
    NextQuestionResult,
    OrchestrationConfig,
    ProgressUpdate,
    TemplateSectionSnapshot,
    TemplateSnapshot,
    TextResponseSignal,
)


# ════════════════════════════════════════════════════════════════════════
# NextQuestionResult
# ════════════════════════════════════════════════════════════════════════


class TestNextQuestionResult:
    def test_valid(self):
        r = NextQuestionResult(
            question_id=101,
            sequence_order=1,
            section_name="resume",
            is_final_question=False,
        )
        assert r.question_id == 101
        assert r.is_final_question is False

    def test_zero_question_id_rejected(self):
        with pytest.raises(Exception):
            NextQuestionResult(
                question_id=0,
                sequence_order=1,
                section_name="resume",
                is_final_question=False,
            )

    def test_zero_sequence_rejected(self):
        with pytest.raises(Exception):
            NextQuestionResult(
                question_id=1,
                sequence_order=0,
                section_name="resume",
                is_final_question=False,
            )

    def test_empty_section_rejected(self):
        with pytest.raises(Exception):
            NextQuestionResult(
                question_id=1,
                sequence_order=1,
                section_name="",
                is_final_question=False,
            )


# ════════════════════════════════════════════════════════════════════════
# ProgressUpdate
# ════════════════════════════════════════════════════════════════════════


class TestProgressUpdate:
    def test_valid(self):
        p = ProgressUpdate(
            submission_id=1,
            current_sequence=5,
            total_questions=10,
            progress_percentage=50.0,
            is_complete=False,
        )
        assert p.progress_percentage == 50.0

    def test_complete(self):
        p = ProgressUpdate(
            submission_id=1,
            current_sequence=10,
            total_questions=10,
            progress_percentage=100.0,
            is_complete=True,
        )
        assert p.is_complete is True

    def test_negative_percentage_rejected(self):
        with pytest.raises(Exception):
            ProgressUpdate(
                submission_id=1,
                current_sequence=0,
                total_questions=10,
                progress_percentage=-1.0,
            )

    def test_over_100_percentage_rejected(self):
        with pytest.raises(Exception):
            ProgressUpdate(
                submission_id=1,
                current_sequence=10,
                total_questions=10,
                progress_percentage=101.0,
            )


# ════════════════════════════════════════════════════════════════════════
# AudioCompletionSignal
# ════════════════════════════════════════════════════════════════════════


class TestAudioCompletionSignal:
    def test_valid(self):
        s = AudioCompletionSignal(
            submission_id=1,
            sequence_order=3,
            recording_id=456,
            transcription_text="I would use a hash map",
            duration_ms=5000,
        )
        assert s.recording_id == 456

    def test_empty_transcription_rejected(self):
        with pytest.raises(Exception):
            AudioCompletionSignal(
                submission_id=1,
                sequence_order=3,
                recording_id=456,
                transcription_text="",
                duration_ms=5000,
            )

    def test_zero_duration_rejected(self):
        with pytest.raises(Exception):
            AudioCompletionSignal(
                submission_id=1,
                sequence_order=3,
                recording_id=456,
                transcription_text="Answer",
                duration_ms=0,
            )


# ════════════════════════════════════════════════════════════════════════
# CodeCompletionSignal
# ════════════════════════════════════════════════════════════════════════


class TestCodeCompletionSignal:
    def test_valid(self):
        s = CodeCompletionSignal(
            submission_id=1,
            sequence_order=5,
            code_submission_id=789,
            code="def solve(): pass",
            language="python",
            execution_status="passed",
            response_time_ms=30000,
        )
        assert s.code_submission_id == 789

    def test_empty_code_rejected(self):
        with pytest.raises(Exception):
            CodeCompletionSignal(
                submission_id=1,
                sequence_order=5,
                code_submission_id=789,
                code="",
                language="python",
                execution_status="passed",
                response_time_ms=30000,
            )


# ════════════════════════════════════════════════════════════════════════
# TextResponseSignal
# ════════════════════════════════════════════════════════════════════════


class TestTextResponseSignal:
    def test_valid(self):
        s = TextResponseSignal(
            submission_id=1,
            sequence_order=2,
            response_text="Polymorphism allows...",
            response_time_ms=45000,
        )
        assert s.response_text == "Polymorphism allows..."

    def test_empty_response_rejected(self):
        with pytest.raises(Exception):
            TextResponseSignal(
                submission_id=1,
                sequence_order=2,
                response_text="",
                response_time_ms=45000,
            )


# ════════════════════════════════════════════════════════════════════════
# OrchestrationConfig
# ════════════════════════════════════════════════════════════════════════


class TestOrchestrationConfig:
    def test_defaults(self):
        c = OrchestrationConfig()
        assert c.exchange_creation_lock_timeout_seconds == 10
        assert c.exchange_max_retries == 3
        assert c.evaluation_trigger_async is True

    def test_override(self):
        c = OrchestrationConfig(
            exchange_creation_lock_timeout_seconds=30,
            progress_redis_ttl_seconds=7200,
        )
        assert c.exchange_creation_lock_timeout_seconds == 30
        assert c.progress_redis_ttl_seconds == 7200

    def test_invalid_lock_timeout(self):
        with pytest.raises(Exception):
            OrchestrationConfig(exchange_creation_lock_timeout_seconds=0)
