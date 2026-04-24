"""
AI Scorer

Scores exchanges using LLM.

Design:
- Uses configured LLM provider for evaluation
- Structured JSON output for consistent parsing
- Retry logic with exponential backoff
- Response validation against rubric dimensions
- No business logic beyond AI interaction

Architecture:
- Takes LLM provider via dependency injection
- Uses PromptService for prompt rendering (optional)
- Returns AIScoreResult with dimension scores
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.ai.llm.base_provider import BaseLLMProvider
from app.ai.llm.contracts import LLMRequest
from app.ai.llm.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMTimeoutError,
    LLMModelNotFoundError,
)
from app.evaluation.scoring.config import get_scoring_config
from app.evaluation.scoring.contracts import (
    AIScoreResult,
    AIScoreResponseSchema,
    DimensionScoreResult,
    RubricDimensionDTO,
)
from app.evaluation.scoring.errors import AIEvaluationError, InvalidScoreError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class AIScorer:
    """
    AI-based scoring using LLM.
    
    Scores candidate responses against rubric dimensions.
    """
    
    # Default prompt template (used if PromptService not available)
    DEFAULT_SYSTEM_PROMPT = (
        "You are a fair, evidence-based interview evaluator. Treat each request as stateless and self-contained. "
        "Use only provided evidence. Do not invent missing details. Award proportional partial credit and avoid overly harsh scoring. "
        "Return JSON only."
    )

    DEFAULT_USER_PROMPT_TEMPLATE = """Evaluate this single exchange.

METADATA:
- answer_length_chars: {answer_length_chars}
- transcript_included: {transcript_included}

QUESTION:
{question_content}

ANSWER:
{answer_content}

{transcript_section}

RUBRIC DIMENSIONS:
{dimensions_text}

RULES:
- Score every dimension from 0 to max_score
- Use exact dimension_name values from input
- Justification must cite concrete evidence from QUESTION/ANSWER/TRANSCRIPT
- Keep each justification concise (10-240 chars)
- Do not repeat the same sentence across dimensions
- If answer_length_chars > 0, do not claim "no response provided"
- Use 0 only when evidence is absent/incorrect for that specific dimension
- If the response is largely correct with minor gaps, avoid low-band scores
- If the response is correct and addresses the question directly, assign at least mid-band scores (>= 60% of max) for relevant correctness dimensions
- For mostly correct answers with minor omissions, prefer upper-mid to high bands (typically 70-85% of max on correctness dimensions)
- Do not penalize minor wording, grammar, accent, or likely STT noise when technical meaning is clear
- Reward demonstrated understanding even if the response is brief
- Do not over-penalize brevity when key reasoning is present
- Return valid JSON only

OUTPUT JSON:
{{"dimension_scores":[{{"dimension_name":"...","score":0,"justification":"..."}}],"overall_comment":"..."}}"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        config: Optional[Any] = None
    ) -> None:
        self._provider = llm_provider
        self._config = config or get_scoring_config()
    
    async def score(
        self,
        question_content: str,
        answer_content: str,
        dimensions: List[RubricDimensionDTO],
        transcript: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> AIScoreResult:
        """
        Score exchange using AI.
        
        Args:
            question_content: Question presented to candidate.
            answer_content: Candidate's answer (text + code).
            dimensions: Rubric dimensions to score against.
            transcript: Optional audio transcript.
            model_id: Override model ID (uses config default if None).
        
        Returns:
            AIScoreResult with dimension scores and overall comment.
        
        Raises:
            AIEvaluationError: LLM failed after all retries.
            InvalidScoreError: AI returned invalid score.
        """
        model = model_id or self._config.evaluation_model
        
        # Build prompt
        prompt = self._build_prompt(
            question_content=question_content,
            answer_content=answer_content,
            dimensions=dimensions,
            transcript=transcript
        )
        
        # Attempt scoring with retries
        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_evaluation_retries):
            try:
                result = await self._call_llm(prompt, model, attempt)
                validated = self._validate_response(result, dimensions)
                
                logger.info(
                    "AI scoring completed",
                    extra={
                        "model": model,
                        "attempt": attempt + 1,
                        "dimension_count": len(validated.dimension_scores)
                    }
                )
                
                return AIScoreResult(
                    dimension_scores=validated.dimension_scores,
                    overall_comment=validated.overall_comment,
                    model_id=model
                )
                
            except (LLMTimeoutError, LLMRateLimitError) as e:
                last_error = e
                delay = self._calculate_retry_delay(attempt, error=e)
                logger.warning(
                    f"AI scoring attempt {attempt + 1} failed, retrying",
                    extra={
                        "error": str(e),
                        "retry_delay": delay,
                        "model": model
                    }
                )
                await asyncio.sleep(delay)

            except LLMModelNotFoundError as e:
                logger.error(
                    "AI scoring failed due to invalid/unavailable model configuration",
                    extra={"error": str(e), "model": model}
                )
                raise AIEvaluationError(
                    message=str(e),
                    provider=self._provider.get_provider_name(),
                    retries_attempted=attempt + 1,
                )

            except LLMProviderError as e:
                if getattr(e, "retryable", False):
                    last_error = e
                    delay = self._calculate_retry_delay(attempt, error=e)
                    logger.warning(
                        f"AI scoring attempt {attempt + 1} failed, retrying",
                        extra={
                            "error": str(e),
                            "retry_delay": delay,
                            "model": model
                        }
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "AI scoring failed with non-retryable provider error",
                        extra={"error": str(e), "model": model}
                    )
                    raise AIEvaluationError(
                        message=str(e),
                        provider=self._provider.get_provider_name(),
                        retries_attempted=attempt + 1,
                    )
                
            except LLMSchemaValidationError as e:
                last_error = e
                logger.warning(
                    f"AI response validation failed on attempt {attempt + 1}",
                    extra={"error": str(e), "model": model}
                )
                # Use shorter delay for schema errors
                await asyncio.sleep(1.0)
        
        # All retries exhausted
        raise AIEvaluationError(
            message=str(last_error) if last_error else "Unknown error",
            provider=self._provider.get_provider_name(),
            retries_attempted=self._config.max_evaluation_retries
        )
    
    def _build_prompt(
        self,
        question_content: str,
        answer_content: str,
        dimensions: List[RubricDimensionDTO],
        transcript: Optional[str]
    ) -> str:
        """Build evaluation prompt."""
        question_text = self._truncate_text(
            text=question_content,
            max_chars=self._config.evaluation_max_question_chars,
        )
        answer_text = self._truncate_text(
            text=answer_content,
            max_chars=self._config.evaluation_max_answer_chars,
        )

        # Format dimensions
        dimensions_text = self._format_dimensions(dimensions)
        
        # Format transcript section
        transcript_section = ""
        transcript_included = "false"
        if transcript and self._config.evaluation_include_transcript:
            transcript_excerpt = self._truncate_text(
                text=transcript,
                max_chars=self._config.evaluation_max_transcript_chars,
            )
            transcript_section = f"TRANSCRIPT (optional excerpt):\n{transcript_excerpt}"
            transcript_included = "true"
        
        # Build prompt from template
        prompt = self.DEFAULT_USER_PROMPT_TEMPLATE.format(
            answer_length_chars=len(answer_text),
            transcript_included=transcript_included,
            question_content=question_text,
            answer_content=answer_text,
            transcript_section=transcript_section,
            dimensions_text=dimensions_text
        )
        
        return prompt
    
    def _format_dimensions(self, dimensions: List[RubricDimensionDTO]) -> str:
        """Format dimensions for prompt."""
        lines = []
        for dim in dimensions:
            line = f"- {dim.dimension_name} | max={dim.max_score} | weight={dim.weight}"
            if dim.description:
                description = self._truncate_text(
                    text=dim.description,
                    max_chars=self._config.evaluation_max_dimension_description_chars,
                )
                line += f"\n  description: {description}"
            if dim.scoring_criteria:
                criteria = self._truncate_text(
                    text=dim.scoring_criteria,
                    max_chars=self._config.evaluation_max_dimension_criteria_chars,
                )
                line += f"\n  criteria: {criteria}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _truncate_text(text: Optional[str], max_chars: int) -> str:
        """Trim text to bounded size for prompt efficiency."""
        if not text:
            return ""
        cleaned = text.strip()
        if max_chars <= 0 or len(cleaned) <= max_chars:
            return cleaned
        return f"{cleaned[:max_chars]}... [truncated]"
    
    async def _call_llm(
        self,
        prompt: str,
        model: str,
        attempt: int
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        request = LLMRequest(
            prompt=prompt,
            model=model,
            system_prompt=self.DEFAULT_SYSTEM_PROMPT,
            temperature=self._config.evaluation_temperature,
            max_tokens=self._config.evaluation_max_tokens,
            timeout_seconds=self._config.evaluation_timeout_seconds,
            json_mode=True,
            schema=AIScoreResponseSchema.get_json_schema(),
            deterministic=True  # For reproducible scoring
        )
        
        response = await self._provider.generate_structured(request)
        
        if not response.success:
            if response.error and response.error.type == "rate_limit":
                raise LLMRateLimitError(
                    provider=self._provider.get_provider_name(),
                    message=response.error.message,
                )
            if response.error and not response.error.retryable and response.error.message:
                error_message = response.error.message.lower()
                if "not found" in error_message or "not supported for generatecontent" in error_message:
                    raise LLMModelNotFoundError(
                        provider=self._provider.get_provider_name(),
                        model_id=model,
                        message=response.error.message,
                    )
            raise LLMProviderError(
                provider=self._provider.get_provider_name(),
                message=response.error.message if response.error else "Unknown error",
                retryable=response.error.retryable if response.error else False,
            )
        
        # Parse JSON response
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            raise LLMSchemaValidationError(
                message=f"Invalid JSON response: {e}",
                actual_response=response.text[:500] if response.text else None
            )
    
    def _validate_response(
        self,
        response: Dict[str, Any],
        dimensions: List[RubricDimensionDTO]
    ) -> AIScoreResult:
        """
        Validate AI response against rubric dimensions.
        
        Validates:
        - All dimensions present
        - No extra dimensions
        - Scores within bounds
        - Justification present
        """
        dimension_scores_raw = response.get("dimension_scores", [])
        overall_comment = response.get("overall_comment", "")
        
        if not dimension_scores_raw:
            raise LLMSchemaValidationError(
                message="No dimension_scores in response"
            )
        
        if not overall_comment:
            overall_comment = "Evaluation completed."
        
        # Build dimension lookup with normalized keys
        dimension_lookup = {
            self._normalize_dimension_key(d.dimension_name): d for d in dimensions
        }
        
        # Validate and convert scores
        validated_scores: List[DimensionScoreResult] = []
        found_dimensions = set()
        unmatched_scores: List[Dict[str, Any]] = []
        
        for score_data in dimension_scores_raw:
            dim_name = score_data.get("dimension_name", "")
            score_value = score_data.get("score", 0)
            justification = score_data.get("justification", "")
            
            # Find matching dimension (normalized)
            dim_key = self._normalize_dimension_key(dim_name)
            if dim_key not in dimension_lookup:
                logger.warning(
                    f"AI returned unknown dimension: {dim_name}",
                    extra={"dimension_name": dim_name}
                )
                unmatched_scores.append(score_data)
                continue

            if dim_key in found_dimensions:
                logger.warning(
                    "AI returned duplicate dimension score; keeping first",
                    extra={"dimension_name": dim_name}
                )
                continue
            
            dimension = dimension_lookup[dim_key]
            found_dimensions.add(dim_key)
            
            # Validate score bounds
            score_decimal = Decimal(str(score_value))
            if score_decimal < 0:
                raise InvalidScoreError(
                    dimension_name=dimension.dimension_name,
                    score=float(score_decimal),
                    max_score=float(dimension.max_score)
                )
            if score_decimal > dimension.max_score:
                # Clamp to max and log warning
                logger.warning(
                    f"AI score exceeds max, clamping",
                    extra={
                        "dimension": dimension.dimension_name,
                        "score": float(score_decimal),
                        "max_score": float(dimension.max_score)
                    }
                )
                score_decimal = dimension.max_score
            
            # Validate justification
            if not justification or len(justification.strip()) < self._config.min_justification_length:
                justification = f"Score of {score_decimal} assigned for {dimension.dimension_name}."
            
            validated_scores.append(DimensionScoreResult(
                dimension_name=dimension.dimension_name,  # Use canonical name
                score=score_decimal,
                justification=justification.strip()
            ))

        # Positional fallback: map unmatched AI scores to still-missing dimensions
        if unmatched_scores:
            missing_keys_in_order = [
                self._normalize_dimension_key(d.dimension_name)
                for d in dimensions
                if self._normalize_dimension_key(d.dimension_name) not in found_dimensions
            ]
            for score_data, dim_key in zip(unmatched_scores, missing_keys_in_order):
                dimension = dimension_lookup[dim_key]
                score_value = score_data.get("score", 0)
                justification = score_data.get("justification", "")

                score_decimal = Decimal(str(score_value))
                if score_decimal < 0:
                    score_decimal = Decimal("0")
                if score_decimal > dimension.max_score:
                    score_decimal = dimension.max_score

                if not justification or len(justification.strip()) < self._config.min_justification_length:
                    justification = f"Score of {score_decimal} assigned for {dimension.dimension_name}."

                validated_scores.append(DimensionScoreResult(
                    dimension_name=dimension.dimension_name,
                    score=score_decimal,
                    justification=justification.strip()
                ))
                found_dimensions.add(dim_key)

                logger.info(
                    "Applied positional fallback for dimension mapping",
                    extra={"mapped_dimension": dimension.dimension_name}
                )

        if not found_dimensions:
            raise LLMSchemaValidationError(
                message="AI response dimensions could not be mapped to rubric dimensions"
            )
        
        # Check for missing dimensions
        missing = set(dimension_lookup.keys()) - found_dimensions
        if missing:
            # For missing dimensions, assign score of 0 with note
            for dim_key in missing:
                dimension = dimension_lookup[dim_key]
                logger.warning(
                    f"AI did not score dimension, assigning 0",
                    extra={"dimension": dimension.dimension_name}
                )
                validated_scores.append(DimensionScoreResult(
                    dimension_name=dimension.dimension_name,
                    score=Decimal("0"),
                    justification="Dimension not evaluated by AI, defaulting to 0."
                ))
        
        return AIScoreResult(
            dimension_scores=validated_scores,
            overall_comment=overall_comment,
            model_id=None  # Set by caller
        )

    @staticmethod
    def _normalize_dimension_key(name: str) -> str:
        """Normalize dimension names for tolerant matching."""
        if not name:
            return ""
        lowered = name.strip().lower()
        return re.sub(r"[^a-z0-9]+", "", lowered)
    
    def _calculate_retry_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        """Calculate retry delay with provider hint support for rate limits."""
        provider_hint = self._extract_retry_after_seconds(error) if error else None
        if provider_hint is not None:
            return min(provider_hint, self._config.retry_max_delay_seconds)

        base = self._config.retry_base_delay_seconds
        max_delay = self._config.retry_max_delay_seconds
        delay = base * (2 ** attempt)
        return min(delay, max_delay)

    @staticmethod
    def _extract_retry_after_seconds(error: Exception) -> Optional[float]:
        """Extract retry-after seconds from provider rate-limit messages."""
        message = str(error)
        match = re.search(r"try again in\s+([0-9]*\.?[0-9]+)\s*(ms|s)", message, re.IGNORECASE)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2).lower()
        seconds = value / 1000.0 if unit == "ms" else value

        # Add tiny cushion to reduce re-hit probability at window boundary.
        return max(0.2, seconds + 0.25)


async def score_with_ai(
    llm_provider: BaseLLMProvider,
    question_content: str,
    answer_content: str,
    dimensions: List[RubricDimensionDTO],
    transcript: Optional[str] = None,
    model_id: Optional[str] = None
) -> AIScoreResult:
    """
    Convenience function for AI scoring.
    
    Args:
        llm_provider: LLM provider instance.
        question_content: Question text.
        answer_content: Candidate answer.
        dimensions: Rubric dimensions.
        transcript: Optional transcript.
        model_id: Override model ID.
    
    Returns:
        AIScoreResult with dimension scores.
    """
    scorer = AIScorer(llm_provider)
    return await scorer.score(
        question_content=question_content,
        answer_content=answer_content,
        dimensions=dimensions,
        transcript=transcript,
        model_id=model_id
    )
