"""
Unit Tests — Clarification Policy

Tests the ClarificationPolicy, ClarificationRequest, ClarificationResponse,
and ClarificationAuditEntry.
"""

from __future__ import annotations

import pytest

from app.interview.exchanges.clarification_policy import (
    CLARIFICATION_PROMPT_CONSTRAINTS,
    ClarificationAuditEntry,
    ClarificationPolicy,
    ClarificationRequest,
    ClarificationResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# ClarificationResponse
# ═══════════════════════════════════════════════════════════════════════════


class TestClarificationResponse:
    def test_word_count_auto_computed(self):
        resp = ClarificationResponse(
            clarification_text="This is a four word response and more",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
        )
        assert resp.word_count == 8

    def test_explicit_word_count_preserved(self):
        resp = ClarificationResponse(
            clarification_text="Two words",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
            word_count=99,  # Explicit override
        )
        assert resp.word_count == 99

    def test_frozen(self):
        resp = ClarificationResponse(
            clarification_text="Test",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
        )
        with pytest.raises(AttributeError):
            resp.violates_policy = True  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════
# ClarificationRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestClarificationRequest:
    def test_defaults(self):
        req = ClarificationRequest(
            original_question="What is BFS?",
            candidate_clarification_request="What do you mean by BFS?",
            clarification_count_so_far=0,
        )
        assert req.allow_hint is False
        assert req.previous_clarifications == []
        assert req.constraints == CLARIFICATION_PROMPT_CONSTRAINTS

    def test_frozen(self):
        req = ClarificationRequest(
            original_question="Test",
            candidate_clarification_request="What?",
            clarification_count_so_far=0,
        )
        with pytest.raises(AttributeError):
            req.allow_hint = True  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════
# ClarificationAuditEntry
# ═══════════════════════════════════════════════════════════════════════════


class TestClarificationAuditEntry:
    def test_to_dict(self):
        entry = ClarificationAuditEntry(
            clarification_number=1,
            candidate_request="What does optimal mean?",
            response_text="Optimal means the best solution in terms of time and space.",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
            word_count=11,
        )
        d = entry.to_dict()
        assert d["clarification_number"] == 1
        assert d["contains_hint"] is False
        assert d["word_count"] == 11


# ═══════════════════════════════════════════════════════════════════════════
# ClarificationPolicy — core behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestClarificationPolicyCore:
    def test_initial_state(self):
        policy = ClarificationPolicy()
        assert policy.clarification_count == 0
        assert policy.can_clarify is True
        assert policy.limit_exceeded is False
        assert policy.audit_log == []

    def test_max_three_clarifications(self):
        """Can request exactly 3 clarifications."""
        policy = ClarificationPolicy()
        for i in range(3):
            req = policy.request_clarification(f"Question {i}")
            assert req is not None
            # Simulate response
            resp = ClarificationResponse(
                clarification_text=f"Clarification {i}",
                contains_hint=False,
                contains_analogy=False,
                violates_policy=False,
            )
            policy.validate_response(resp)

        assert policy.clarification_count == 3
        assert policy.limit_exceeded is True
        assert policy.can_clarify is False

    def test_fourth_request_returns_none(self):
        """Fourth clarification request returns None (limit exceeded)."""
        policy = ClarificationPolicy()
        for i in range(3):
            req = policy.request_clarification(f"Q{i}")
            resp = ClarificationResponse(
                clarification_text=f"A{i}",
                contains_hint=False,
                contains_analogy=False,
                violates_policy=False,
            )
            policy.validate_response(resp)

        result = policy.request_clarification("One more please")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# ClarificationPolicy — validation
# ═══════════════════════════════════════════════════════════════════════════


class TestClarificationPolicyValidation:
    def test_word_count_violation(self):
        """Response exceeding MAX_WORDS is flagged."""
        policy = ClarificationPolicy()
        policy.request_clarification("What?")

        long_text = " ".join(["word"] * 150)  # 150 words > 120 max
        resp = ClarificationResponse(
            clarification_text=long_text,
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
            word_count=150,
        )
        validated = policy.validate_response(resp)
        assert validated.violates_policy is True

    def test_analogy_limit(self):
        """Second analogy is a violation."""
        policy = ClarificationPolicy()

        # First analogy — allowed
        policy.request_clarification("Q1")
        resp1 = ClarificationResponse(
            clarification_text="Like sorting cards",
            contains_hint=False,
            contains_analogy=True,
            violates_policy=False,
        )
        result1 = policy.validate_response(resp1)
        assert result1.violates_policy is False

        # Second analogy — violation
        policy.request_clarification("Q2")
        resp2 = ClarificationResponse(
            clarification_text="Like building blocks",
            contains_hint=False,
            contains_analogy=True,
            violates_policy=False,
        )
        result2 = policy.validate_response(resp2)
        assert result2.violates_policy is True

    def test_hint_violation(self):
        """Hints are forbidden by default."""
        policy = ClarificationPolicy()
        policy.request_clarification("Help")

        resp = ClarificationResponse(
            clarification_text="Think about recursion",
            contains_hint=True,
            contains_analogy=False,
            violates_policy=False,  # Will be corrected
        )
        validated = policy.validate_response(resp)
        assert validated.violates_policy is True

    def test_compliant_response(self):
        """Valid response passes all checks."""
        policy = ClarificationPolicy()
        policy.request_clarification("What does efficient mean?")

        resp = ClarificationResponse(
            clarification_text="Efficient means minimizing resource usage.",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
        )
        validated = policy.validate_response(resp)
        assert validated.violates_policy is False


# ═══════════════════════════════════════════════════════════════════════════
# ClarificationPolicy — audit
# ═══════════════════════════════════════════════════════════════════════════


class TestClarificationPolicyAudit:
    def test_audit_log_populated(self):
        """Each validated response creates an audit entry."""
        policy = ClarificationPolicy()
        policy.request_clarification("Q1")
        resp = ClarificationResponse(
            clarification_text="Answer 1",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
        )
        policy.validate_response(resp)

        assert len(policy.audit_log) == 1
        assert policy.audit_log[0].clarification_number == 1

    def test_to_audit_dict(self):
        policy = ClarificationPolicy()
        policy.request_clarification("Q1")
        resp = ClarificationResponse(
            clarification_text="Answer 1",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
        )
        policy.validate_response(resp)

        d = policy.to_audit_dict()
        assert d["clarification_count"] == 1
        assert d["clarification_limit_exceeded"] is False
        assert d["hint_given"] is False
        assert d["analogy_given"] is False
        assert len(d["clarifications"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# CLARIFICATION_PROMPT_CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════════════


class TestPromptConstraints:
    def test_max_words(self):
        assert CLARIFICATION_PROMPT_CONSTRAINTS["MAX_WORDS"] == 120

    def test_hints_disabled(self):
        assert CLARIFICATION_PROMPT_CONSTRAINTS["ALLOW_HINT"] is False

    def test_prohibitions_complete(self):
        prohibitions = CLARIFICATION_PROMPT_CONSTRAINTS["PROHIBITIONS"]
        assert "algorithm_suggestions" in prohibitions
        assert "data_structure_suggestions" in prohibitions
        assert "step_sequencing" in prohibitions
        assert "partial_validation" in prohibitions
        assert "encouraging_phrases" in prohibitions
        assert "answer_description" in prohibitions
        assert "solution_examples" in prohibitions
