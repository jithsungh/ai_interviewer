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
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.ai.llm.base_provider import BaseLLMProvider
from app.ai.llm.contracts import LLMRequest
from app.ai.llm.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMTimeoutError,
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
    DEFAULT_SYSTEM_PROMPT = """You are an expert interviewer evaluating candidate responses.
Your task is to score the response against each rubric dimension objectively and consistently.
Be fair, balanced, and provide clear justification for each score."""

    DEFAULT_USER_PROMPT_TEMPLATE = """Evaluate the following candidate response:

**Question:**
{question_content}

**Candidate's Answer:**
{answer_content}

{transcript_section}

**Rubric Dimensions to Evaluate:**
{dimensions_text}

**Instructions:**
1. Evaluate the response against EACH dimension separately
2. Assign a score between 0 and the max_score for each dimension
3. Provide concise justification for each score (minimum 10 characters)
4. Be consistent and objective

**Output Format (JSON):**
{{"dimension_scores": [{{"dimension_name": "...", "score": X.X, "justification": "..."}}], "overall_comment": "..."}}"""

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
                
            except (LLMTimeoutError, LLMRateLimitError, LLMProviderError) as e:
                last_error = e
                delay = self._calculate_retry_delay(attempt)
                logger.warning(
                    f"AI scoring attempt {attempt + 1} failed, retrying",
                    extra={
                        "error": str(e),
                        "retry_delay": delay,
                        "model": model
                    }
                )
                await asyncio.sleep(delay)
                
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
        # Format dimensions
        dimensions_text = self._format_dimensions(dimensions)
        
        # Format transcript section
        transcript_section = ""
        if transcript:
            transcript_section = f"\n**Audio Transcript:**\n{transcript}\n"
        
        # Build prompt from template
        prompt = self.DEFAULT_USER_PROMPT_TEMPLATE.format(
            question_content=question_content,
            answer_content=answer_content,
            transcript_section=transcript_section,
            dimensions_text=dimensions_text
        )
        
        return prompt
    
    def _format_dimensions(self, dimensions: List[RubricDimensionDTO]) -> str:
        """Format dimensions for prompt."""
        lines = []
        for dim in dimensions:
            line = f"- **{dim.dimension_name}** (max score: {dim.max_score}, weight: {dim.weight})"
            if dim.description:
                line += f"\n  Description: {dim.description}"
            if dim.scoring_criteria:
                line += f"\n  Criteria: {dim.scoring_criteria}"
            lines.append(line)
        return "\n".join(lines)
    
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
            raise LLMProviderError(
                provider=self._provider.get_provider_name(),
                message=response.error.message if response.error else "Unknown error"
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
        
        # Build dimension lookup
        dimension_lookup = {d.dimension_name.lower(): d for d in dimensions}
        
        # Validate and convert scores
        validated_scores: List[DimensionScoreResult] = []
        found_dimensions = set()
        
        for score_data in dimension_scores_raw:
            dim_name = score_data.get("dimension_name", "")
            score_value = score_data.get("score", 0)
            justification = score_data.get("justification", "")
            
            # Find matching dimension (case-insensitive)
            dim_key = dim_name.lower()
            if dim_key not in dimension_lookup:
                logger.warning(
                    f"AI returned unknown dimension: {dim_name}",
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
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        base = self._config.retry_base_delay_seconds
        max_delay = self._config.retry_max_delay_seconds
        delay = base * (2 ** attempt)
        return min(delay, max_delay)


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
