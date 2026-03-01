"""
Question Generation Service — Main Orchestrator

Coordinates:
1. Prompt assembly (via app.ai.prompts.PromptService)
2. LLM call (via app.ai.llm.BaseLLMProvider)
3. Response parsing (domain/parsing)
4. Post-generation validation (domain/validation)
5. Fallback to generic questions (persistence/fallback_repository)
6. Telemetry & audit metadata

This service is STATELESS — safe for concurrent calls.
It does NOT persist exchanges, does NOT orchestrate interviews.

Consumed by: question/selection module or interview module.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import List, Optional

from app.ai.llm.base_provider import BaseLLMProvider
from app.ai.llm.contracts import LLMRequest, LLMResponse
from app.ai.llm.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.ai.llm.utils.token_counter import estimate_cost, estimate_tokens
from app.ai.prompts.entities import RenderedPrompt
from app.ai.prompts.errors import PromptNotFoundError
from app.ai.prompts.service import PromptService
from app.question.generation.contracts import (
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
)
from app.question.generation.domain.entities import (
    GeneratedQuestionOutput,
    GenerationMetadata,
    ValidationResult,
)
from app.question.generation.domain.parsing import (
    ResponseParseError,
    parse_llm_response,
)
from app.question.generation.domain.validation import validate_generated_question
from app.question.generation.persistence.fallback_repository import (
    FallbackQuestionRepository,
)

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════════

_PROMPT_TYPE = "question_generation"
_DEFAULT_TIMEOUT_S = 30
_BACKOFF_BASE_S = 1.0


class QuestionGenerationService:
    """
    Generates interview questions via LLM with validation and fallback.

    Args:
        llm_provider: LLM text-generation provider (Groq, OpenAI, …)
        prompt_service: Prompt template retrieval & rendering
        fallback_repo: Optional repo for generic fallback questions.
                       If None, fallback is disabled.
        embedding_provider: Optional embedding provider for similarity
                            checking. If None, similarity check is skipped.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        prompt_service: PromptService,
        fallback_repo: Optional[FallbackQuestionRepository] = None,
        embedding_provider=None,  # BaseEmbeddingProvider, optional
    ) -> None:
        self._llm = llm_provider
        self._prompts = prompt_service
        self._fallback_repo = fallback_repo
        self._embedding_provider = embedding_provider

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a question from the LLM with retry + validation + fallback.

        Workflow:
          1. Render prompt template with request context
          2. Call LLM with structured JSON mode
          3. Parse response into GeneratedQuestionOutput
          4. Validate (difficulty, topic, substance, similarity)
          5. On validation failure → stricter retry
          6. After max retries → fallback to generic pool
          7. Return GenerationResult with full audit metadata

        Returns GenerationResult with status indicating outcome.
        Never raises — all errors are captured in the result.
        """
        overall_start = time.perf_counter()
        total_prompt_tokens = 0
        total_completion_tokens = 0
        all_failures: List[str] = []
        last_similarity = 0.0

        # ----------------------------------------------------------
        # Step 1: Render prompt
        # ----------------------------------------------------------
        try:
            rendered = self._render_prompt(request)
        except (PromptNotFoundError, Exception) as exc:
            logger.error(
                "Prompt rendering failed for submission %d: %s",
                request.submission_id,
                exc,
            )
            return self._try_fallback(
                request,
                reason=f"prompt_error: {type(exc).__name__}",
                all_failures=["prompt_rendering_failed"],
                overall_start=overall_start,
            )

        prompt_hash = self._compute_prompt_hash(rendered)
        prompt_version = rendered.version

        # ----------------------------------------------------------
        # Step 2-5: LLM call loop with retries
        # ----------------------------------------------------------
        for attempt in range(1, request.max_retries + 1):
            logger.info(
                "Generation attempt %d/%d for submission %d "
                "(difficulty=%s, topic=%s)",
                attempt,
                request.max_retries,
                request.submission_id,
                request.difficulty,
                request.topic,
            )

            # 2. Call LLM
            try:
                llm_response = await self._call_llm(rendered, request)
            except (LLMTimeoutError, LLMRateLimitError, LLMProviderError) as exc:
                fail_msg = f"llm_{type(exc).__name__}_attempt_{attempt}"
                all_failures.append(fail_msg)
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt,
                    request.max_retries,
                    exc,
                )
                if attempt < request.max_retries:
                    await self._backoff(attempt)
                continue

            # Accumulate token counts
            if llm_response.telemetry:
                total_prompt_tokens += llm_response.telemetry.prompt_tokens
                total_completion_tokens += llm_response.telemetry.completion_tokens

            if not llm_response.success or not llm_response.text:
                fail_msg = f"llm_no_text_attempt_{attempt}"
                all_failures.append(fail_msg)
                logger.warning(
                    "LLM returned failure/empty on attempt %d", attempt
                )
                if attempt < request.max_retries:
                    await self._backoff(attempt)
                continue

            # 3. Parse response
            try:
                output = parse_llm_response(llm_response.text)
            except ResponseParseError as exc:
                fail_msg = f"parse_error_attempt_{attempt}: {exc}"
                all_failures.append(fail_msg)
                logger.warning("Parse failed (attempt %d): %s", attempt, exc)
                if attempt < request.max_retries:
                    await self._backoff(attempt)
                continue

            # 4. Validate
            new_embedding = await self._generate_embedding_safe(
                output.question_text
            )
            validation = validate_generated_question(
                output=output,
                requested_difficulty=request.difficulty,
                allowed_topics=[request.topic],
                previous_question_embeddings=request.previous_question_embeddings,
                new_embedding=new_embedding,
                similarity_threshold=request.similarity_threshold,
            )
            last_similarity = validation.similarity_score

            if validation.passed:
                # 5. Success!
                elapsed_ms = (time.perf_counter() - overall_start) * 1000
                cost = estimate_cost(
                    total_prompt_tokens,
                    total_completion_tokens,
                    self._get_model_id(rendered),
                ) or 0.0

                logger.info(
                    "Question generated successfully for submission %d "
                    "(attempts=%d, latency_ms=%.1f)",
                    request.submission_id,
                    attempt,
                    elapsed_ms,
                )

                return GenerationResult(
                    status=GenerationStatus.SUCCESS,
                    question_text=output.question_text,
                    expected_answer=output.expected_answer,
                    difficulty=output.difficulty,
                    topic=output.topic,
                    subtopic=output.subtopic,
                    question_type=request.question_type,
                    estimated_time_seconds=output.estimated_time_seconds,
                    skill_tags=output.skill_tags,
                    source_type="generated",
                    prompt_hash=prompt_hash,
                    llm_model=self._get_model_id(rendered),
                    llm_provider=self._llm.get_provider_name(),
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    estimated_cost_usd=cost,
                    generation_latency_ms=elapsed_ms,
                    attempts=attempt,
                    validation_failures=all_failures,
                    similarity_score=last_similarity,
                    prompt_version=prompt_version,
                )
            else:
                all_failures.extend(validation.failures)
                logger.warning(
                    "Validation failed (attempt %d): %s",
                    attempt,
                    validation.failure_summary,
                )

        # ----------------------------------------------------------
        # Step 6: Fallback
        # ----------------------------------------------------------
        return self._try_fallback(
            request,
            reason="max_retries_exhausted",
            all_failures=all_failures,
            overall_start=overall_start,
            prompt_hash=prompt_hash,
            prompt_version=prompt_version,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            similarity_score=last_similarity,
        )

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Prompt rendering
    # ══════════════════════════════════════════════════════════════════

    def _render_prompt(self, request: GenerationRequest) -> RenderedPrompt:
        """Build variable map and render the question_generation prompt."""
        previously_asked = "\n".join(
            f"- {q}" for q in request.previous_questions
        ) or "None (first question)"

        candidate_context = ""
        if request.resume_text:
            candidate_context += f"Resume summary:\n{request.resume_text}\n"
        if request.job_description:
            candidate_context += f"Job description:\n{request.job_description}\n"
        if not candidate_context:
            candidate_context = "No candidate context available."

        variables = {
            "role": request.question_type,
            "topic": request.topic,
            "subtopic": request.subtopic or request.topic,
            "difficulty": request.difficulty,
            "question_type": request.question_type,
            "remaining_time_minutes": str(
                request.remaining_time_minutes or 30
            ),
            "exchange_number": str(request.exchange_number or 1),
            "total_exchanges": str(request.total_exchanges or 10),
            "candidate_context": candidate_context,
            "last_score_percent": str(
                int(request.last_score_percent)
                if request.last_score_percent is not None
                else "N/A"
            ),
            "performance_trend": request.performance_trend or "stable",
            "previously_asked": previously_asked,
            "rubric_dimensions": request.rubric_dimensions
            or "Standard rubric (clarity, accuracy, depth)",
        }

        return self._prompts.get_rendered_prompt(
            prompt_type=_PROMPT_TYPE,
            variables=variables,
            organization_id=request.organization_id,
            fallback_to_global=True,
            truncate_context=True,
            max_context_tokens=6000,
        )

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — LLM call
    # ══════════════════════════════════════════════════════════════════

    async def _call_llm(
        self,
        rendered: RenderedPrompt,
        request: GenerationRequest,
    ) -> LLMResponse:
        """Call LLM provider in JSON structured mode."""
        model_id = self._get_model_id(rendered)
        temperature = rendered.temperature or 0.7
        max_tokens = rendered.max_tokens or 1500

        llm_request = LLMRequest(
            prompt=rendered.text,
            model=model_id,
            system_prompt=rendered.system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            timeout_seconds=_DEFAULT_TIMEOUT_S,
            organization_id=request.organization_id,
        )

        return await self._llm.generate_structured(llm_request)

    def _get_model_id(self, rendered: RenderedPrompt) -> str:
        """Resolve model ID from rendered prompt config or settings."""
        model = rendered.model_config.get("model")
        if model:
            return model
        # Fallback: use settings
        try:
            from app.config.settings import settings as _settings

            if _settings:
                return _settings.llm.llm_model_question_generation
        except Exception:
            pass
        return "llama-3.3-70b-versatile"

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Embedding (optional similarity check)
    # ══════════════════════════════════════════════════════════════════

    async def _generate_embedding_safe(
        self, text: str
    ) -> Optional[List[float]]:
        """
        Generate embedding for similarity check.
        Returns None if provider unavailable or fails (non-blocking).
        """
        if self._embedding_provider is None:
            return None
        try:
            from app.ai.llm.contracts import EmbeddingRequest

            resp = await self._embedding_provider.generate_embedding(
                EmbeddingRequest(text=text)
            )
            return resp.embedding if resp.success else None
        except Exception as exc:
            logger.warning("Embedding generation failed (non-blocking): %s", exc)
            return None

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Fallback
    # ══════════════════════════════════════════════════════════════════

    def _try_fallback(
        self,
        request: GenerationRequest,
        *,
        reason: str,
        all_failures: List[str],
        overall_start: float,
        prompt_hash: Optional[str] = None,
        prompt_version: Optional[int] = None,
        total_prompt_tokens: int = 0,
        total_completion_tokens: int = 0,
        similarity_score: float = 0.0,
    ) -> GenerationResult:
        """
        Attempt to load a generic fallback question from the DB.

        Search hierarchy:
          1. difficulty + topic
          2. difficulty only
          3. any active fallback
        """
        elapsed_ms = (time.perf_counter() - overall_start) * 1000

        if self._fallback_repo is None:
            logger.error(
                "No fallback repo configured for submission %d — "
                "returning NO_FALLBACK",
                request.submission_id,
            )
            return GenerationResult(
                status=GenerationStatus.NO_FALLBACK,
                source_type="none",
                fallback_reason=f"{reason} (no fallback repo)",
                generation_latency_ms=elapsed_ms,
                attempts=request.max_retries,
                validation_failures=all_failures,
                prompt_hash=prompt_hash,
                prompt_version=prompt_version,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                similarity_score=similarity_score,
            )

        # Try: difficulty + topic → difficulty only → any active
        fb = self._fallback_repo.get_by_difficulty_and_topic(
            request.difficulty, request.topic
        )
        if fb is None:
            fb = self._fallback_repo.get_by_difficulty(request.difficulty)
        if fb is None:
            fb = self._fallback_repo.get_any_active()

        if fb is None:
            logger.error(
                "No fallback questions available for submission %d",
                request.submission_id,
            )
            return GenerationResult(
                status=GenerationStatus.NO_FALLBACK,
                source_type="none",
                fallback_reason=f"{reason} (fallback pool empty)",
                generation_latency_ms=elapsed_ms,
                attempts=request.max_retries,
                validation_failures=all_failures,
                prompt_hash=prompt_hash,
                prompt_version=prompt_version,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                similarity_score=similarity_score,
            )

        # Increment usage count
        try:
            self._fallback_repo.increment_usage(fb.id)
        except Exception as exc:
            logger.warning("Failed to increment fallback usage: %s", exc)

        logger.info(
            "Fallback question loaded for submission %d "
            "(fallback_id=%d, reason=%s)",
            request.submission_id,
            fb.id,
            reason,
        )

        return GenerationResult(
            status=GenerationStatus.FALLBACK_USED,
            question_text=fb.question_text,
            expected_answer=fb.expected_answer,
            difficulty=fb.difficulty,
            topic=fb.topic,
            question_type=request.question_type,
            estimated_time_seconds=fb.estimated_time_seconds,
            source_type="fallback_generic",
            fallback_question_id=fb.id,
            fallback_reason=reason,
            generation_latency_ms=elapsed_ms,
            attempts=request.max_retries,
            validation_failures=all_failures,
            prompt_hash=prompt_hash,
            prompt_version=prompt_version,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            similarity_score=similarity_score,
        )

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Utilities
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _compute_prompt_hash(rendered: RenderedPrompt) -> str:
        """SHA-256 of combined system + user prompt for deduplication."""
        combined = (rendered.system_prompt or "") + rendered.text
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    async def _backoff(attempt: int) -> None:
        """Async-compatible exponential backoff."""
        import asyncio

        delay = _BACKOFF_BASE_S * (2 ** (attempt - 1))
        await asyncio.sleep(min(delay, 8.0))
