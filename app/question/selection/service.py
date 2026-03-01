"""
Question Selection Service — Main Orchestrator

Coordinates:
1. Template snapshot parsing
2. Difficulty adaptation (FR-3.2, FR-4.3, FR-4.4)
3. Retrieval via Qdrant (delegates to retrieval module)
4. Repetition prevention (FR-4.5)
5. Fallback strategies (relax difficulty/topic, LLM generation)
6. Adaptation decision logging (audit trail)

This service is STATELESS — safe for concurrent calls.
It does NOT persist exchanges (interview module does that).
It does NOT orchestrate interviews.
It returns frozen QuestionSnapshot objects.

Consumed by: interview module.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.question.generation.contracts import GenerationRequest, GenerationResult
from app.question.generation.service import QuestionGenerationService
from app.question.retrieval.contracts import (
    DifficultyLevel,
    QuestionCandidate,
    RetrievalResult,
    SearchCriteria,
)
from app.question.retrieval.service import QdrantRetrievalService
from app.question.selection.contracts import (
    AdaptationDecision,
    CandidateProfile,
    DifficultyAdaptationConfig,
    ExchangeHistoryEntry,
    FallbackType,
    QuestionSnapshot,
    RepetitionConfig,
    SectionConfig,
    SelectionContext,
    SelectionResult,
    SelectionStrategy,
)
from app.question.selection.domain.difficulty import (
    RULE_VERSION,
    adapt_difficulty,
    build_adaptation_decision,
)
from app.question.selection.domain.fallback import (
    MAX_FALLBACK_ATTEMPTS,
    get_fallback_type,
    get_relaxed_difficulties,
)
from app.question.selection.domain.repetition import (
    check_repetition,
)
from app.question.selection.domain.template_parser import (
    SectionCompleteError,
    TemplateSnapshotError,
    find_section,
    get_last_exchange_in_section,
    parse_adaptation_config,
    validate_template_snapshot,
)
from app.question.selection.persistence.adaptation_repository import (
    AdaptationLogRepository,
)

logger = logging.getLogger(__name__)


class NoQuestionAvailableError(Exception):
    """Raised when no question can be selected after all fallbacks."""

    def __init__(self, message: str = "No question available"):
        self.message = message
        super().__init__(message)


class QuestionSelectionService:
    """
    Main question selection orchestrator.

    Lifecycle:
        Instantiated per-request (or injected as scoped dependency).
        Retrieval and generation services are injected.
        Adaptation log repository requires per-request DB session.

    Args:
        retrieval_service: Qdrant retrieval service.
        generation_service: LLM generation service (optional).
        adaptation_repo: Repository for logging adaptation decisions (optional).
    """

    def __init__(
        self,
        retrieval_service: QdrantRetrievalService,
        generation_service: Optional[QuestionGenerationService] = None,
        adaptation_repo: Optional[AdaptationLogRepository] = None,
    ) -> None:
        self._retrieval = retrieval_service
        self._generation = generation_service
        self._adaptation_repo = adaptation_repo

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════

    def select_next_question(
        self,
        context: SelectionContext,
        repetition_config: Optional[RepetitionConfig] = None,
    ) -> SelectionResult:
        """
        Select the next question based on template and context.

        Workflow:
          1. Validate & parse template snapshot
          2. Find current section config
          3. Check remaining question count
          4. Adapt difficulty (if enabled)
          5. Retrieve candidate questions
          6. Filter repetitions
          7. Fallback if needed
          8. Build and return QuestionSnapshot

        Args:
            context: SelectionContext with all input data.
            repetition_config: Optional repetition configuration.

        Returns:
            SelectionResult with question snapshot and metadata.

        Raises:
            TemplateSnapshotError: Malformed template.
            SectionCompleteError: Section already has all questions.
            NoQuestionAvailableError: Exhausted all strategies.
        """
        start_time = time.monotonic()
        rep_config = repetition_config or RepetitionConfig()

        # Step 1: Validate template snapshot
        validate_template_snapshot(context.template_snapshot)

        # Step 2: Find current section
        section_config = find_section(
            context.template_snapshot, context.current_section
        )
        if section_config is None:
            raise TemplateSnapshotError(
                f"Section '{context.current_section}' not found in template"
            )

        # Step 3: Count remaining questions
        history_dicts = self._history_to_dicts(context.exchange_history)
        section_exchanges = [
            e
            for e in history_dicts
            if e.get("section_name") == context.current_section
        ]
        remaining = section_config.question_count - len(section_exchanges)

        if remaining <= 0:
            raise SectionCompleteError(
                section_name=context.current_section,
                asked=len(section_exchanges),
                total=section_config.question_count,
            )

        # Step 4: Determine target difficulty
        adaptation_config = parse_adaptation_config(
            context.template_snapshot
        )
        target_difficulty, adaptation_reason, adaptation_decision = (
            self._determine_difficulty(
                context=context,
                section_config=section_config,
                adaptation_config=adaptation_config,
                history_dicts=history_dicts,
            )
        )

        # Step 5: Retrieve candidates
        candidates = self._retrieve_candidates(
            context=context,
            section_config=section_config,
            target_difficulty=target_difficulty,
        )

        # Step 6: Filter repetitions
        filtered = self._filter_repetitions(
            candidates=candidates,
            history_dicts=history_dicts,
            config=rep_config,
        )

        # Step 7: Select or fallback
        if filtered:
            selected = filtered[0]
            snapshot = self._candidate_to_snapshot(
                candidate=selected,
                section_config=section_config,
                strategy=section_config.selection_strategy,
                metadata={
                    "candidates_count": len(candidates),
                    "after_deduplication": len(filtered),
                    "adaptation_reason": adaptation_reason,
                    "target_difficulty": target_difficulty,
                },
            )
            result = SelectionResult(
                question_snapshot=snapshot,
                selection_metadata={
                    "duration_ms": (time.monotonic() - start_time) * 1000,
                    "section": context.current_section,
                    "remaining_in_section": remaining - 1,
                },
                adaptation_decision=adaptation_decision,
            )
        else:
            # Fallback
            logger.warning(
                "All candidates rejected for submission=%d section=%s "
                "— entering fallback",
                context.submission_id,
                context.current_section,
            )
            result = self._fallback_selection(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_decision=adaptation_decision,
                adaptation_reason=adaptation_reason,
                rep_config=rep_config,
            )

        # Step 8: Log adaptation decision
        if adaptation_decision and self._adaptation_repo:
            try:
                self._adaptation_repo.log_decision(adaptation_decision)
            except Exception:
                logger.exception(
                    "Failed to log adaptation decision for submission=%d",
                    context.submission_id,
                )

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "Question selected: submission=%d section=%s "
            "question_id=%s strategy=%s difficulty=%s (%.1f ms)",
            context.submission_id,
            context.current_section,
            result.question_snapshot.question_id,
            result.question_snapshot.selection_strategy,
            result.question_snapshot.difficulty,
            duration_ms,
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Difficulty Adaptation
    # ══════════════════════════════════════════════════════════════════

    def _determine_difficulty(
        self,
        context: SelectionContext,
        section_config: SectionConfig,
        adaptation_config: DifficultyAdaptationConfig,
        history_dicts: List[Dict[str, Any]],
    ) -> tuple[str, str, Optional[AdaptationDecision]]:
        """
        Determine the target difficulty for the next question.

        Returns:
            (target_difficulty, reason, adaptation_decision_or_None)
        """
        strategy = section_config.selection_strategy

        if strategy == "adaptive" and adaptation_config.enabled:
            # Find last exchange in this section
            last_exchange = get_last_exchange_in_section(
                history_dicts, context.current_section
            )

            if last_exchange and last_exchange.get("evaluation_score") is not None:
                prev_difficulty = last_exchange.get("difficulty", "medium")
                prev_score = last_exchange.get("evaluation_score")
                prev_q_id = last_exchange.get("question_id")

                target_difficulty, reason = adapt_difficulty(
                    previous_difficulty=prev_difficulty,
                    previous_score=prev_score,
                    config=adaptation_config,
                )

                decision = build_adaptation_decision(
                    submission_id=context.submission_id,
                    exchange_sequence_order=context.exchange_sequence_order,
                    previous_difficulty=prev_difficulty,
                    previous_score=prev_score,
                    previous_question_id=prev_q_id,
                    next_difficulty=target_difficulty,
                    adaptation_reason=reason,
                    config=adaptation_config,
                )

                return (target_difficulty, reason, decision)
            else:
                # First question in section — use default
                default_diff = (
                    section_config.difficulty_range[0]
                    if section_config.difficulty_range
                    else "medium"
                )
                reason = "first_question_in_section"

                decision = build_adaptation_decision(
                    submission_id=context.submission_id,
                    exchange_sequence_order=context.exchange_sequence_order,
                    previous_difficulty=None,
                    previous_score=None,
                    previous_question_id=None,
                    next_difficulty=default_diff,
                    adaptation_reason=reason,
                    config=adaptation_config,
                )
                return (default_diff, reason, decision)
        else:
            # Non-adaptive — use first difficulty in range
            target = (
                section_config.difficulty_range[0]
                if section_config.difficulty_range
                else "medium"
            )
            return (target, "static_difficulty", None)

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Retrieval
    # ══════════════════════════════════════════════════════════════════

    def _retrieve_candidates(
        self,
        context: SelectionContext,
        section_config: SectionConfig,
        target_difficulty: str,
    ) -> List[QuestionCandidate]:
        """
        Retrieve candidate questions via retrieval module.

        Uses semantic search if candidate profile has embeddings,
        otherwise falls back to topic-based or static search.
        """
        # Build exclude list from history
        asked_ids = [
            e.question_id
            for e in context.exchange_history
            if e.question_id is not None
        ]

        # Map difficulty string to enum
        try:
            diff_enum = DifficultyLevel(target_difficulty)
        except ValueError:
            diff_enum = None

        # Determine query vector
        query_vector = None
        if context.candidate_profile:
            if context.candidate_profile.resume_embedding:
                query_vector = context.candidate_profile.resume_embedding

        # Build search criteria
        criteria = SearchCriteria(
            organization_id=context.organization_id,
            query_vector=query_vector,
            difficulty=diff_enum,
            topic_ids=None,  # Topic filtering via Qdrant metadata
            question_type=section_config.question_type,
            top_k=10,
            score_threshold=0.3,
            exclude_question_ids=asked_ids,
            include_public=True,
        )

        # Search
        strategy = section_config.selection_strategy
        if strategy == "semantic_retrieval" and query_vector is not None:
            result: RetrievalResult = self._retrieval.search_semantic(
                criteria
            )
        else:
            # Topic-based or static pool
            result = self._retrieval.search_by_topic(criteria)

        return result.candidates

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Repetition Filtering
    # ══════════════════════════════════════════════════════════════════

    def _filter_repetitions(
        self,
        candidates: List[QuestionCandidate],
        history_dicts: List[Dict[str, Any]],
        config: RepetitionConfig,
    ) -> List[QuestionCandidate]:
        """
        Remove candidates that are too similar to previously asked questions.
        """
        filtered = []
        for candidate in candidates:
            # Get embedding for candidate (via retrieval service)
            embedding = self._get_candidate_embedding(candidate)

            is_repeat, similarity = check_repetition(
                candidate_question_id=candidate.question_id,
                candidate_embedding=embedding,
                exchange_history=history_dicts,
                config=config,
            )

            if not is_repeat:
                filtered.append(candidate)
            else:
                logger.info(
                    "Rejected candidate question_id=%d (similarity=%.3f)",
                    candidate.question_id,
                    similarity,
                )

        return filtered

    def _get_candidate_embedding(
        self, candidate: QuestionCandidate
    ) -> Optional[List[float]]:
        """
        Try to retrieve embedding for a candidate from Qdrant.

        Returns None if unavailable (graceful degradation).
        """
        try:
            return self._retrieval.get_embedding_vector(
                source_type="question",
                source_id=candidate.question_id,
                organization_id=1,  # Qdrant stores all under one collection
            )
        except Exception:
            return None

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Fallback
    # ══════════════════════════════════════════════════════════════════

    def _fallback_selection(
        self,
        context: SelectionContext,
        section_config: SectionConfig,
        target_difficulty: str,
        adaptation_decision: Optional[AdaptationDecision],
        adaptation_reason: str,
        rep_config: RepetitionConfig,
        attempt: int = 0,
    ) -> SelectionResult:
        """
        Progressive fallback when primary selection fails.

        Hierarchy:
          0: Relax difficulty (try all difficulties)
          1: Relax topic (remove topic filter)
          2: Relax similarity threshold
          3: LLM generation
          4: Generic fallback question

        Raises:
            NoQuestionAvailableError after all attempts exhausted.
        """
        if attempt >= MAX_FALLBACK_ATTEMPTS:
            raise NoQuestionAvailableError(
                f"Exhausted all {MAX_FALLBACK_ATTEMPTS} fallback strategies "
                f"for submission={context.submission_id} "
                f"section={context.current_section}"
            )

        fallback_type = get_fallback_type(attempt)
        logger.warning(
            "Fallback attempt %d (%s) for submission=%d section=%s",
            attempt,
            fallback_type.value if fallback_type else "unknown",
            context.submission_id,
            context.current_section,
        )

        asked_ids = [
            e.question_id
            for e in context.exchange_history
            if e.question_id is not None
        ]

        # Attempt 0: Relax difficulty
        if fallback_type == FallbackType.RELAXED_DIFFICULTY:
            for diff in get_relaxed_difficulties(target_difficulty):
                try:
                    diff_enum = DifficultyLevel(diff)
                except ValueError:
                    continue

                criteria = SearchCriteria(
                    organization_id=context.organization_id,
                    difficulty=diff_enum,
                    question_type=section_config.question_type,
                    top_k=10,
                    score_threshold=0.1,
                    exclude_question_ids=asked_ids,
                    include_public=True,
                )
                result = self._retrieval.search_by_topic(criteria)

                filtered = self._filter_repetitions(
                    result.candidates,
                    self._history_to_dicts(context.exchange_history),
                    rep_config,
                )

                if filtered:
                    snapshot = self._candidate_to_snapshot(
                        candidate=filtered[0],
                        section_config=section_config,
                        strategy="static_pool",
                        metadata={
                            "fallback_type": "relaxed_difficulty",
                            "original_difficulty": target_difficulty,
                            "actual_difficulty": diff,
                            "adaptation_reason": adaptation_reason,
                        },
                    )
                    return SelectionResult(
                        question_snapshot=snapshot,
                        adaptation_decision=adaptation_decision,
                        fallback_used=True,
                        fallback_type="relaxed_difficulty",
                    )

            # Fall through to next attempt
            return self._fallback_selection(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_decision=adaptation_decision,
                adaptation_reason=adaptation_reason,
                rep_config=rep_config,
                attempt=attempt + 1,
            )

        # Attempt 1: Relax topic (remove topic filter → broader search)
        if fallback_type == FallbackType.RELAXED_TOPIC:
            criteria = SearchCriteria(
                organization_id=context.organization_id,
                difficulty=None,  # No difficulty restriction
                topic_ids=None,  # No topic restriction
                top_k=20,
                score_threshold=0.1,
                exclude_question_ids=asked_ids,
                include_public=True,
            )
            result = self._retrieval.search_by_topic(criteria)

            filtered = self._filter_repetitions(
                result.candidates,
                self._history_to_dicts(context.exchange_history),
                rep_config,
            )

            if filtered:
                snapshot = self._candidate_to_snapshot(
                    candidate=filtered[0],
                    section_config=section_config,
                    strategy="static_pool",
                    metadata={
                        "fallback_type": "relaxed_topic",
                        "adaptation_reason": adaptation_reason,
                    },
                )
                return SelectionResult(
                    question_snapshot=snapshot,
                    adaptation_decision=adaptation_decision,
                    fallback_used=True,
                    fallback_type="relaxed_topic",
                )

            return self._fallback_selection(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_decision=adaptation_decision,
                adaptation_reason=adaptation_reason,
                rep_config=rep_config,
                attempt=attempt + 1,
            )

        # Attempt 2: Relax similarity threshold
        if fallback_type == FallbackType.RELAXED_SIMILARITY:
            relaxed_config = RepetitionConfig(
                enable_exact_match_check=True,
                enable_semantic_check=True,
                similarity_threshold_similar=rep_config.relaxed_similarity_threshold,
            )
            criteria = SearchCriteria(
                organization_id=context.organization_id,
                difficulty=None,
                top_k=20,
                score_threshold=0.1,
                exclude_question_ids=asked_ids,
                include_public=True,
            )
            result = self._retrieval.search_by_topic(criteria)

            filtered = self._filter_repetitions(
                result.candidates,
                self._history_to_dicts(context.exchange_history),
                relaxed_config,
            )

            if filtered:
                snapshot = self._candidate_to_snapshot(
                    candidate=filtered[0],
                    section_config=section_config,
                    strategy="static_pool",
                    metadata={
                        "fallback_type": "relaxed_similarity",
                        "relaxed_threshold": rep_config.relaxed_similarity_threshold,
                        "adaptation_reason": adaptation_reason,
                    },
                )
                return SelectionResult(
                    question_snapshot=snapshot,
                    adaptation_decision=adaptation_decision,
                    fallback_used=True,
                    fallback_type="relaxed_similarity",
                )

            return self._fallback_selection(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_decision=adaptation_decision,
                adaptation_reason=adaptation_reason,
                rep_config=rep_config,
                attempt=attempt + 1,
            )

        # Attempt 3: LLM Generation
        if fallback_type == FallbackType.LLM_GENERATION:
            snapshot = self._try_generation(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_reason=adaptation_reason,
            )
            if snapshot:
                return SelectionResult(
                    question_snapshot=snapshot,
                    adaptation_decision=adaptation_decision,
                    fallback_used=True,
                    fallback_type="llm_generation",
                )

            return self._fallback_selection(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_decision=adaptation_decision,
                adaptation_reason=adaptation_reason,
                rep_config=rep_config,
                attempt=attempt + 1,
            )

        # Attempt 4: Generic fallback
        if fallback_type == FallbackType.GENERIC_FALLBACK:
            snapshot = self._try_generation(
                context=context,
                section_config=section_config,
                target_difficulty=target_difficulty,
                adaptation_reason=adaptation_reason,
                use_generic=True,
            )
            if snapshot:
                return SelectionResult(
                    question_snapshot=snapshot,
                    adaptation_decision=adaptation_decision,
                    fallback_used=True,
                    fallback_type="generic_fallback",
                )

        raise NoQuestionAvailableError(
            f"All fallback strategies exhausted for submission="
            f"{context.submission_id}"
        )

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Generation
    # ══════════════════════════════════════════════════════════════════

    def _try_generation(
        self,
        context: SelectionContext,
        section_config: SectionConfig,
        target_difficulty: str,
        adaptation_reason: str,
        use_generic: bool = False,
    ) -> Optional[QuestionSnapshot]:
        """
        Attempt LLM question generation (async call handled synchronously).

        Returns None if generation service unavailable or fails.
        """
        if self._generation is None:
            logger.warning(
                "Generation service not available — skipping generation"
            )
            return None

        try:
            topic = (
                section_config.topic_constraints[0]
                if section_config.topic_constraints
                else "general"
            )

            previous_texts = [
                e.question_text for e in context.exchange_history
            ]

            request = GenerationRequest(
                submission_id=context.submission_id,
                organization_id=context.organization_id,
                difficulty=target_difficulty,
                topic=topic,
                question_type=section_config.question_type,
                resume_text=(
                    context.candidate_profile.resume_text
                    if context.candidate_profile
                    else None
                ),
                job_description=(
                    context.candidate_profile.job_description
                    if context.candidate_profile
                    else None
                ),
                template_instructions=section_config.template_instructions,
                previous_questions=previous_texts,
                exchange_number=context.exchange_sequence_order,
            )

            # Generation service is async — this must be called from an
            # async context. For synchronous callers, this is wrapped by
            # the API layer with asyncio.
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context — use create_task workaround
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    gen_result: GenerationResult = pool.submit(
                        asyncio.run, self._generation.generate(request)
                    ).result(timeout=30)
            else:
                gen_result = asyncio.run(
                    self._generation.generate(request)
                )

            if gen_result.is_success and gen_result.question_text:
                return QuestionSnapshot(
                    question_id=None,  # Generated, not from DB
                    question_type=gen_result.question_type
                    or section_config.question_type,
                    question_text=gen_result.question_text,
                    expected_answer=gen_result.expected_answer,
                    difficulty=gen_result.difficulty or target_difficulty,
                    topic_name=gen_result.topic or topic,
                    estimated_time_seconds=gen_result.estimated_time_seconds
                    or 300,
                    selection_strategy=SelectionStrategy.GENERATION.value,
                    selection_metadata={
                        "source_type": gen_result.source_type,
                        "llm_model": gen_result.llm_model,
                        "prompt_hash": gen_result.prompt_hash,
                        "generation_latency_ms": gen_result.generation_latency_ms,
                        "adaptation_reason": adaptation_reason,
                    },
                    selected_at=datetime.utcnow(),
                    selection_rule_version=RULE_VERSION,
                )

            logger.warning(
                "Generation failed: status=%s, attempting next fallback",
                gen_result.status.value,
            )
            return None

        except Exception:
            logger.exception(
                "Generation error for submission=%d",
                context.submission_id,
            )
            return None

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Helpers
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _history_to_dicts(
        history: List[ExchangeHistoryEntry],
    ) -> List[Dict[str, Any]]:
        """Convert typed exchange history to dicts for domain functions."""
        return [
            {
                "question_id": e.question_id,
                "coding_problem_id": e.coding_problem_id,
                "question_text": e.question_text,
                "difficulty": e.difficulty,
                "section_name": e.section_name,
                "evaluation_score": e.evaluation_score,
                "question_embedding": e.question_embedding,
                "sequence_order": e.sequence_order,
            }
            for e in history
        ]

    @staticmethod
    def _candidate_to_snapshot(
        candidate: QuestionCandidate,
        section_config: SectionConfig,
        strategy: str,
        metadata: Dict[str, Any],
    ) -> QuestionSnapshot:
        """
        Build a QuestionSnapshot from a retrieval QuestionCandidate.

        Note: question_text and expected_answer are NOT in QuestionCandidate
        (it only has question_id + similarity_score). The interview module
        must resolve the full question data from the DB using question_id.

        For the snapshot, we set question_text to a placeholder that the
        interview module will resolve from the questions table.
        """
        return QuestionSnapshot(
            question_id=candidate.question_id,
            question_type=section_config.question_type,
            question_text=f"[resolve:question:{candidate.question_id}]",
            expected_answer=None,
            difficulty=candidate.difficulty or "medium",
            topic_name=None,
            estimated_time_seconds=300,
            selection_strategy=strategy,
            selection_metadata=metadata,
            selected_at=datetime.utcnow(),
            selection_rule_version=RULE_VERSION,
        )
