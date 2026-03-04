"""
Question Prompt Assembler — Main entry point

Orchestrates the full prompt assembly pipeline:
1. Load prompt template from ``prompt_templates`` table
2. Sanitize candidate-provided inputs
3. Detect prompt injection attempts
4. Estimate tokens for each context piece
5. Prioritize and fit within budget
6. Render template with actual values via ``PromptService``
7. Validate final prompt structure
8. Return prompt + metadata

References:
- prompting/REQUIREMENTS.md §7.1 (Full assembly workflow)
- app.ai.prompts.service (PromptService for template loading + rendering)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.prompts.entities import RenderedPrompt
from app.ai.prompts.service import PromptService
from app.question.prompting.config import PromptConfig
from app.question.prompting.context import prioritize_context
from app.question.prompting.safety import (
    PromptInjectionError,
    sanitize_text,
    validate_input_safety,
)
from app.question.prompting.tokens import TokenEstimator

logger = logging.getLogger(__name__)

# Prompt type key stored in the prompt_templates table.
_PROMPT_TYPE = "question_generation"


@dataclass(frozen=True)
class PromptAssemblyResult:
    """
    Output of the prompt assembly pipeline.

    Contains the rendered prompt plus audit metadata for observability.
    """

    rendered_prompt: RenderedPrompt
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def system_prompt(self) -> Optional[str]:
        return self.rendered_prompt.system_prompt

    @property
    def user_prompt(self) -> str:
        return self.rendered_prompt.text

    @property
    def total_tokens(self) -> int:
        return self.metadata.get("total_tokens", 0)

    @property
    def truncated_fields(self) -> List[str]:
        return self.metadata.get("truncated_fields", [])


class QuestionPromptAssembler:
    """
    Assembles structured prompts for LLM question generation.

    Depends on:
    - ``PromptService`` — loads and renders templates from database.
    - ``PromptConfig``  — configurable token budgets and safety flags.

    Usage::

        assembler = QuestionPromptAssembler(prompt_service=prompt_svc)
        result = assembler.assemble(
            difficulty="medium",
            topic="binary trees",
            resume_text="Python developer with 5 years...",
            job_description="Senior backend engineer...",
        )
        # result.system_prompt, result.user_prompt ready for LLM
    """

    def __init__(
        self,
        prompt_service: PromptService,
        config: Optional[PromptConfig] = None,
    ) -> None:
        self._prompt_service = prompt_service
        self._config = config or PromptConfig()
        self._estimator = TokenEstimator(model=self._config.token_model)

    def assemble(
        self,
        *,
        difficulty: str,
        topic: str,
        submission_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        resume_text: Optional[str] = None,
        job_description: Optional[str] = None,
        previous_exchanges: Optional[List[Dict[str, Any]]] = None,
        template_instructions: str = "",
        allowed_topics: Optional[List[str]] = None,
        estimated_time: Optional[int] = None,
    ) -> PromptAssemblyResult:
        """
        Assemble a complete prompt for LLM question generation.

        Args:
            difficulty: Target difficulty level (easy / medium / hard).
            topic: Target topic name.
            submission_id: Interview submission ID (for audit trail).
            organization_id: Organization ID (for template resolution).
            resume_text: Raw candidate resume text (will be sanitized).
            job_description: Raw job description text (will be sanitized).
            previous_exchanges: List of dicts with 'topic' and 'question_text' keys.
            template_instructions: Section-specific instructions from interview template.
            allowed_topics: Allowed topic names (for validation constraint).
            estimated_time: Estimated answer time in seconds.

        Returns:
            PromptAssemblyResult with rendered prompt and metadata.

        Raises:
            PromptInjectionError: If injection patterns detected.
            PromptNotFoundError: If no active template found.
            VariableMissingError: If template requires variables not provided.
        """
        logger.info(
            "Prompt assembly started",
            extra={
                "submission_id": submission_id,
                "difficulty": difficulty,
                "topic": topic,
            },
        )

        # ── Step 1: Sanitize inputs ────────────────────────────────

        safe_resume = ""
        if resume_text and self._config.enable_sanitization:
            safe_resume = sanitize_text(
                resume_text, max_length=self._config.max_resume_chars
            )
        elif resume_text:
            safe_resume = resume_text

        safe_jd = ""
        if job_description and self._config.enable_sanitization:
            safe_jd = sanitize_text(
                job_description, max_length=self._config.max_jd_chars
            )
        elif job_description:
            safe_jd = job_description

        # ── Step 2: Detect injection ───────────────────────────────

        if self._config.enable_injection_detection:
            validate_input_safety(
                resume_text=safe_resume,
                job_description=safe_jd,
            )

        # ── Step 3: Prepare previous exchange summaries ────────────

        exchange_summaries: List[str] = []
        if previous_exchanges:
            for ex in previous_exchanges[-self._config.max_previous_exchanges :]:
                t = ex.get("topic", "unknown")
                q = ex.get("question_text", "")[:80]
                exchange_summaries.append(f"- {t}: {q}...")

        # ── Step 4: Prioritize context for token budget ────────────

        context = prioritize_context(
            template_instructions=template_instructions,
            difficulty=difficulty,
            topic=topic,
            previous_exchanges=exchange_summaries,
            job_description=safe_jd,
            resume_text=safe_resume,
            max_tokens=self._config.available_context_tokens,
            token_model=self._config.token_model,
            max_previous_exchanges=self._config.max_previous_exchanges,
        )

        # Add extra template variables
        if allowed_topics:
            context["allowed_topics"] = ", ".join(allowed_topics)
        if estimated_time is not None:
            context["estimated_time"] = str(estimated_time)

        # ── Step 5: Render template via PromptService ──────────────

        rendered = self._prompt_service.get_rendered_prompt(
            prompt_type=self._config.prompt_type,
            organization_id=organization_id or 1,
            variables=context,
        )

        # ── Step 6: Validate total token count ─────────────────────

        full_text = rendered.text
        if rendered.system_prompt:
            full_text = rendered.system_prompt + "\n" + full_text

        total_tokens = self._estimator.estimate(full_text)

        # Determine which fields were truncated
        truncated_fields = [
            k
            for k in ("previous_topics", "job_description", "resume_truncated")
            if "[truncated]" in context.get(k, "")
        ]

        metadata: Dict[str, Any] = {
            "total_tokens": total_tokens,
            "prompt_template_version": rendered.version,
            "prompt_type": rendered.prompt_type,
            "variables_used": rendered.variables_used,
            "truncated_fields": truncated_fields,
            "submission_id": submission_id,
            "organization_id": organization_id,
            "was_truncated": rendered.truncated or bool(truncated_fields),
        }

        logger.info(
            "Prompt assembly complete",
            extra={
                "total_tokens": total_tokens,
                "truncated_fields": truncated_fields,
                "template_version": rendered.version,
                "submission_id": submission_id,
            },
        )

        return PromptAssemblyResult(
            rendered_prompt=rendered,
            metadata=metadata,
        )
