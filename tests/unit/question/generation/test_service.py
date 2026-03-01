"""
Unit Tests — QuestionGenerationService

Tests the async generate() orchestrator with fully mocked dependencies:
- BaseLLMProvider (async)
- PromptService (sync, returns RenderedPrompt)
- FallbackQuestionRepository (sync, returns GenericFallbackQuestion)
- Embedding provider (async, optional)

Each test covers a distinct scenario in the retry/fallback/success flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.llm.contracts import LLMRequest, LLMResponse, TelemetryData, LLMError
from app.ai.llm.errors import LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.ai.prompts.entities import RenderedPrompt
from app.ai.prompts.errors import PromptNotFoundError
from app.question.generation.contracts import (
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
)
from app.question.generation.persistence.models import GenericFallbackQuestion
from app.question.generation.service import QuestionGenerationService


# ════════════════════════════════════════════════════════════════════════════
# Helpers & Factories
# ════════════════════════════════════════════════════════════════════════════


def _make_request(**overrides) -> GenerationRequest:
    """Factory for a minimal valid GenerationRequest."""
    defaults = dict(
        submission_id=1,
        organization_id=42,
        difficulty="medium",
        topic="algorithms",
        max_retries=3,
    )
    defaults.update(overrides)
    return GenerationRequest(**defaults)


def _make_rendered_prompt(**overrides) -> RenderedPrompt:
    """Factory for a RenderedPrompt."""
    return RenderedPrompt(
        text=overrides.get("text", "Generate a question about algorithms."),
        system_prompt=overrides.get("system_prompt", "You are an interviewer."),
        model_config=overrides.get("model_config", {"model": "llama-3.3-70b-versatile"}),
        version=overrides.get("version", 1),
        prompt_type="question_generation",
    )


def _make_llm_json(**overrides) -> str:
    """Build a valid LLM JSON response string."""
    data = {
        "question_text": "What is the time complexity of quicksort?",
        "expected_answer": "Average O(n log n), worst O(n^2).",
        "difficulty": "medium",
        "topic": "algorithms",
    }
    data.update(overrides)
    return json.dumps(data)


def _make_llm_response(
    text: Optional[str] = None,
    success: bool = True,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> LLMResponse:
    """Factory for an LLMResponse."""
    telemetry = TelemetryData(
        model_id="llama-3.3-70b-versatile",
        provider="groq",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=200,
        success=success,
    )
    if success:
        return LLMResponse(
            success=True,
            text=text or _make_llm_json(),
            telemetry=telemetry,
        )
    else:
        return LLMResponse(
            success=False,
            text=None,
            telemetry=telemetry,
            error=LLMError(
                type="provider_error",
                message="provider failure",
                retryable=True,
            ),
        )


def _make_fallback(**overrides) -> GenericFallbackQuestion:
    """Factory for a GenericFallbackQuestion ORM object."""
    fb = GenericFallbackQuestion()
    fb.id = overrides.get("id", 99)
    fb.question_text = overrides.get(
        "question_text", "Describe a challenging project."
    )
    fb.expected_answer = overrides.get(
        "expected_answer", "Candidate provides a structured answer."
    )
    fb.difficulty = overrides.get("difficulty", "medium")
    fb.topic = overrides.get("topic", "general")
    fb.estimated_time_seconds = overrides.get("estimated_time_seconds", 120)
    fb.question_type = overrides.get("question_type", "behavioral")
    fb.is_active = True
    fb.usage_count = 0
    return fb


def _build_service(
    llm_provider=None,
    prompt_service=None,
    fallback_repo=None,
    embedding_provider=None,
) -> QuestionGenerationService:
    """Build service with mocked dependencies (sensible defaults)."""
    if llm_provider is None:
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response()
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

    if prompt_service is None:
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            return_value=_make_rendered_prompt()
        )

    return QuestionGenerationService(
        llm_provider=llm_provider,
        prompt_service=prompt_service,
        fallback_repo=fallback_repo,
        embedding_provider=embedding_provider,
    )


# ════════════════════════════════════════════════════════════════════════════
# Tests — Successful generation
# ════════════════════════════════════════════════════════════════════════════


class TestSuccessfulGeneration:
    """Tests where LLM returns valid output on first attempt."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        svc = _build_service()
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
        assert result.question_text == "What is the time complexity of quicksort?"
        assert result.difficulty == "medium"
        assert result.source_type == "generated"
        assert result.attempts == 1
        assert result.prompt_tokens > 0
        assert result.llm_model == "llama-3.3-70b-versatile"
        assert result.llm_provider == "groq"

    @pytest.mark.asyncio
    async def test_success_includes_prompt_hash(self):
        svc = _build_service()
        result = await svc.generate(_make_request())

        assert result.prompt_hash is not None
        assert len(result.prompt_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_success_includes_latency(self):
        svc = _build_service()
        result = await svc.generate(_make_request())

        assert result.generation_latency_ms > 0

    @pytest.mark.asyncio
    async def test_success_records_prompt_version(self):
        svc = _build_service()
        result = await svc.generate(_make_request())

        assert result.prompt_version == 1

    @pytest.mark.asyncio
    async def test_no_validation_failures_on_success(self):
        svc = _build_service()
        result = await svc.generate(_make_request())

        assert result.validation_failures == []

    @pytest.mark.asyncio
    async def test_optional_fields_in_response(self):
        """Verify subtopic, skill_tags, estimated_time from LLM output."""
        llm_json = _make_llm_json(
            subtopic="sorting",
            skill_tags=["algorithms", "analysis"],
            estimated_time_seconds=180,
        )
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response(text=llm_json)
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
        assert result.subtopic == "sorting"
        assert result.estimated_time_seconds == 180


# ════════════════════════════════════════════════════════════════════════════
# Tests — Retry behaviour
# ════════════════════════════════════════════════════════════════════════════


class TestRetryBehaviour:
    """Tests where the first attempt(s) fail but a retry succeeds."""

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt_after_llm_error(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                LLMProviderError(provider="groq", message="temporary failure"),
                _make_llm_response(),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
        assert result.attempts == 2
        assert any("LLMProviderError" in f for f in result.validation_failures)

    @pytest.mark.asyncio
    async def test_succeeds_after_parse_error(self):
        """First attempt returns malformed JSON, second attempt is valid."""
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                _make_llm_response(text="not valid json"),
                _make_llm_response(),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_succeeds_after_empty_response(self):
        """LLM returns success=False on first try."""
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                _make_llm_response(success=False),
                _make_llm_response(),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_backoff_called_between_retries(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                LLMTimeoutError(provider="groq", timeout_seconds=30),
                _make_llm_response(),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock) as mock_backoff:
            result = await svc.generate(_make_request())

        mock_backoff.assert_awaited_once_with(1)
        assert result.status == GenerationStatus.SUCCESS


# ════════════════════════════════════════════════════════════════════════════
# Tests — Fallback
# ════════════════════════════════════════════════════════════════════════════


class TestFallback:
    """Tests where all LLM attempts fail ⇒ fallback path activated."""

    @pytest.mark.asyncio
    async def test_fallback_after_all_retries_exhausted(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(
            return_value=_make_fallback()
        )
        fallback_repo.increment_usage = MagicMock()

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=fallback_repo
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.FALLBACK_USED
        assert result.source_type == "fallback_generic"
        assert result.fallback_question_id == 99
        assert result.fallback_reason == "max_retries_exhausted"
        fallback_repo.increment_usage.assert_called_once_with(99)

    @pytest.mark.asyncio
    async def test_fallback_cascades_difficulty_only(self):
        """
        difficulty+topic miss → difficulty only hit.
        """
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        fb = _make_fallback(topic="general")
        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(return_value=None)
        fallback_repo.get_by_difficulty = MagicMock(return_value=fb)
        fallback_repo.increment_usage = MagicMock()

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=fallback_repo
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.FALLBACK_USED
        fallback_repo.get_by_difficulty.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_cascades_any_active(self):
        """
        difficulty+topic miss → difficulty miss → any active hit.
        """
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        fb = _make_fallback(difficulty="easy", topic="general")
        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(return_value=None)
        fallback_repo.get_by_difficulty = MagicMock(return_value=None)
        fallback_repo.get_any_active = MagicMock(return_value=fb)
        fallback_repo.increment_usage = MagicMock()

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=fallback_repo
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.FALLBACK_USED
        fallback_repo.get_any_active.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_fallback_when_pool_empty(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(return_value=None)
        fallback_repo.get_by_difficulty = MagicMock(return_value=None)
        fallback_repo.get_any_active = MagicMock(return_value=None)

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=fallback_repo
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.NO_FALLBACK
        assert "fallback pool empty" in result.fallback_reason

    @pytest.mark.asyncio
    async def test_no_fallback_when_repo_not_configured(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=None
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.NO_FALLBACK
        assert "no fallback repo" in result.fallback_reason

    @pytest.mark.asyncio
    async def test_increment_usage_failure_non_blocking(self):
        """increment_usage exception is logged but does not break."""
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(
            return_value=_make_fallback()
        )
        fallback_repo.increment_usage = MagicMock(side_effect=Exception("db error"))

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=fallback_repo
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        # Still returns fallback despite increment failure
        assert result.status == GenerationStatus.FALLBACK_USED


# ════════════════════════════════════════════════════════════════════════════
# Tests — Prompt rendering failures
# ════════════════════════════════════════════════════════════════════════════


class TestPromptFailure:
    """Tests where prompt rendering fails ⇒ immediate fallback."""

    @pytest.mark.asyncio
    async def test_prompt_not_found_triggers_fallback(self):
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            side_effect=PromptNotFoundError(prompt_type="question_generation")
        )

        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(
            return_value=_make_fallback()
        )
        fallback_repo.increment_usage = MagicMock()

        svc = _build_service(
            prompt_service=prompt_service, fallback_repo=fallback_repo
        )
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.FALLBACK_USED
        assert "prompt_error" in result.fallback_reason

    @pytest.mark.asyncio
    async def test_prompt_generic_error_triggers_fallback(self):
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            side_effect=RuntimeError("unexpected")
        )

        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(
            return_value=_make_fallback()
        )
        fallback_repo.increment_usage = MagicMock()

        svc = _build_service(
            prompt_service=prompt_service, fallback_repo=fallback_repo
        )
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.FALLBACK_USED

    @pytest.mark.asyncio
    async def test_prompt_failure_no_fallback_repo(self):
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            side_effect=PromptNotFoundError(prompt_type="question_generation")
        )

        svc = _build_service(
            prompt_service=prompt_service, fallback_repo=None
        )
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.NO_FALLBACK


# ════════════════════════════════════════════════════════════════════════════
# Tests — Token / cost tracking
# ════════════════════════════════════════════════════════════════════════════


class TestTokenAndCostTracking:
    """Verify token accumulators across retries."""

    @pytest.mark.asyncio
    async def test_tokens_accumulated_across_retries(self):
        """Two LLM calls → tokens from both should be summed."""
        resp1 = _make_llm_response(text="bad json", prompt_tokens=50, completion_tokens=20)
        resp2 = _make_llm_response(prompt_tokens=60, completion_tokens=30)

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[resp1, resp2]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        # resp1 has bad json → parse fail → tokens still counted
        # resp2 is good → success on attempt 2
        assert result.status == GenerationStatus.SUCCESS
        assert result.prompt_tokens == 110  # 50 + 60
        assert result.completion_tokens == 50  # 20 + 30


# ════════════════════════════════════════════════════════════════════════════
# Tests — Validation failures within retry loop
# ════════════════════════════════════════════════════════════════════════════


class TestValidationInRetryLoop:
    """Test generation where parsed output fails validation checks."""

    @pytest.mark.asyncio
    async def test_difficulty_mismatch_causes_retry(self):
        """LLM returns 'hard' but request asks 'medium' → validation fail → retry."""
        bad_json = _make_llm_json(difficulty="hard")
        good_json = _make_llm_json(difficulty="medium")

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                _make_llm_response(text=bad_json),
                _make_llm_response(text=good_json),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request(difficulty="medium"))

        assert result.status == GenerationStatus.SUCCESS
        assert result.attempts == 2
        # First attempt should have a difficulty_mismatch failure
        assert any("difficulty" in f.lower() for f in result.validation_failures)

    @pytest.mark.asyncio
    async def test_all_validation_failures_lead_to_fallback(self):
        """3 attempts all produce wrong difficulty → fallback."""
        bad_json = _make_llm_json(difficulty="hard")

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response(text=bad_json)
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        fallback_repo = MagicMock()
        fallback_repo.get_by_difficulty_and_topic = MagicMock(
            return_value=_make_fallback()
        )
        fallback_repo.increment_usage = MagicMock()

        svc = _build_service(
            llm_provider=llm_provider, fallback_repo=fallback_repo
        )

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request(difficulty="medium"))

        assert result.status == GenerationStatus.FALLBACK_USED


# ════════════════════════════════════════════════════════════════════════════
# Tests — LLM error types
# ════════════════════════════════════════════════════════════════════════════


class TestLLMErrorTypes:

    @pytest.mark.asyncio
    async def test_rate_limit_retried(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                LLMRateLimitError(provider="groq", message="rate limited"),
                _make_llm_response(),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_timeout_retried(self):
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=[
                LLMTimeoutError(provider="groq", timeout_seconds=30),
                _make_llm_response(),
            ]
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(llm_provider=llm_provider)

        with patch.object(svc, "_backoff", new_callable=AsyncMock):
            result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS


# ════════════════════════════════════════════════════════════════════════════
# Tests — Prompt rendering (variable mapping)
# ════════════════════════════════════════════════════════════════════════════


class TestPromptRendering:
    """Verify the _render_prompt variable mapping is correct."""

    @pytest.mark.asyncio
    async def test_render_prompt_passes_correct_variables(self):
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            return_value=_make_rendered_prompt()
        )

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response()
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(
            llm_provider=llm_provider, prompt_service=prompt_service
        )
        request = _make_request(
            topic="data_structures",
            subtopic="linked lists",
            difficulty="hard",
            exchange_number=5,
            total_exchanges=10,
        )
        await svc.generate(request)

        call_kwargs = prompt_service.get_rendered_prompt.call_args
        variables = call_kwargs.kwargs.get("variables") or call_kwargs[1].get("variables")

        assert variables["topic"] == "data_structures"
        assert variables["subtopic"] == "linked lists"
        assert variables["difficulty"] == "hard"
        assert variables["exchange_number"] == "5"
        assert variables["total_exchanges"] == "10"

    @pytest.mark.asyncio
    async def test_render_prompt_defaults_for_missing_context(self):
        """Missing subtopic → defaults to topic; missing exchange → defaults."""
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            return_value=_make_rendered_prompt()
        )

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response()
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(
            llm_provider=llm_provider, prompt_service=prompt_service
        )
        request = _make_request(topic="algorithms")  # no subtopic
        await svc.generate(request)

        call_kwargs = prompt_service.get_rendered_prompt.call_args
        variables = call_kwargs.kwargs.get("variables") or call_kwargs[1].get("variables")

        # subtopic defaults to topic
        assert variables["subtopic"] == "algorithms"
        # exchange_number defaults to "1"
        assert variables["exchange_number"] == "1"

    @pytest.mark.asyncio
    async def test_resume_and_jd_included_in_context(self):
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            return_value=_make_rendered_prompt()
        )

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response()
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(
            llm_provider=llm_provider, prompt_service=prompt_service
        )
        request = _make_request(
            resume_text="Python dev, 5 years",
            job_description="Backend engineer role",
        )
        await svc.generate(request)

        call_kwargs = prompt_service.get_rendered_prompt.call_args
        variables = call_kwargs.kwargs.get("variables") or call_kwargs[1].get("variables")

        assert "Python dev" in variables["candidate_context"]
        assert "Backend engineer" in variables["candidate_context"]

    @pytest.mark.asyncio
    async def test_previous_questions_listed(self):
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            return_value=_make_rendered_prompt()
        )

        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            return_value=_make_llm_response()
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        svc = _build_service(
            llm_provider=llm_provider, prompt_service=prompt_service
        )
        request = _make_request(
            previous_questions=["Q1?", "Q2?"],
        )
        await svc.generate(request)

        call_kwargs = prompt_service.get_rendered_prompt.call_args
        variables = call_kwargs.kwargs.get("variables") or call_kwargs[1].get("variables")

        assert "Q1?" in variables["previously_asked"]
        assert "Q2?" in variables["previously_asked"]


# ════════════════════════════════════════════════════════════════════════════
# Tests — Embedding integration (optional)
# ════════════════════════════════════════════════════════════════════════════


class TestEmbeddingIntegration:

    @pytest.mark.asyncio
    async def test_embedding_failure_non_blocking(self):
        """Embedding provider fails → generation still succeeds."""
        embedding_provider = AsyncMock()
        embedding_provider.generate_embedding = AsyncMock(
            side_effect=RuntimeError("embedding service down")
        )

        svc = _build_service(embedding_provider=embedding_provider)
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_no_embedding_provider_still_succeeds(self):
        """When embedding_provider is None, similarity check is skipped."""
        svc = _build_service(embedding_provider=None)
        result = await svc.generate(_make_request())

        assert result.status == GenerationStatus.SUCCESS
