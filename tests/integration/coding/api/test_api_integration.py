"""
Integration tests for the coding/api module — service layer.

These tests hit a real PostgreSQL database to validate:
- CodingApiService.submit_code() — end-to-end create + authorization
- CodingApiService.get_execution_status() — hidden test filtering
- CodingApiService.list_submissions_for_interview() — cross-exchange listing
- Authorization enforcement (candidate ownership, admin bypass)
- Conflict detection (duplicate submission)

Requires:
- PostgreSQL with interviewer schema + coding migrations applied
- Set TEST_DATABASE_URL env-var to override the default test-cluster address

Each test runs within a transactional session that is **always rolled back**.
"""

import pytest
from sqlalchemy import text

from app.coding.api.service import CodingApiService
from app.coding.api.contracts import (
    ExecutionStatusResponse,
    SubmissionSummary,
    SubmitCodeResponse,
)
from app.shared.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


# ====================================================================
# Submit Code — happy path + validations
# ====================================================================


class TestSubmitCode:
    """Integration tests for CodingApiService.submit_code()."""

    def test_submit_creates_pending_submission(
        self, db_session, coding_seed, candidate_identity,
    ):
        """Successful submission returns pending status."""
        svc = CodingApiService(db_session)
        result = svc.submit_code(
            identity=candidate_identity,
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        assert isinstance(result, SubmitCodeResponse)
        assert result.submission_id is not None
        assert result.execution_status == "pending"

    def test_submit_duplicate_raises_conflict(
        self, db_session, coding_seed, candidate_identity,
    ):
        """Second submission for same exchange raises ConflictError."""
        svc = CodingApiService(db_session)

        svc.submit_code(
            identity=candidate_identity,
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(1)",
        )

        with pytest.raises(ConflictError):
            svc.submit_code(
                identity=candidate_identity,
                interview_exchange_id=coding_seed["exchange_id"],
                coding_problem_id=coding_seed["coding_problem_id"],
                language="python3",
                source_code="print(2)",
            )

    def test_submit_wrong_problem_id_raises_validation(
        self, db_session, coding_seed, candidate_identity,
    ):
        """Mismatched coding_problem_id raises ValidationError."""
        svc = CodingApiService(db_session)

        with pytest.raises(ValidationError):
            svc.submit_code(
                identity=candidate_identity,
                interview_exchange_id=coding_seed["exchange_id"],
                coding_problem_id=999999,  # wrong
                language="python3",
                source_code="print(1)",
            )

    def test_submit_nonexistent_exchange_raises_not_found(
        self, db_session, coding_seed, candidate_identity,
    ):
        """Non-existent exchange raises NotFoundError."""
        svc = CodingApiService(db_session)

        with pytest.raises(NotFoundError):
            svc.submit_code(
                identity=candidate_identity,
                interview_exchange_id=999999,
                coding_problem_id=coding_seed["coding_problem_id"],
                language="python3",
                source_code="print(1)",
            )

    def test_submit_wrong_candidate_raises_authorization(
        self, db_session, coding_seed, _unique_suffix,
    ):
        """Candidate who doesn't own the exchange is rejected."""
        from app.shared.auth_context import IdentityContext

        # Create a different user
        other_user_id = db_session.execute(
            text(
                "INSERT INTO users (name, email, password_hash, user_type) "
                "VALUES (:name, :email, :pw, :utype) RETURNING id"
            ),
            {
                "name": "Other Candidate",
                "email": f"other-{_unique_suffix}@seed.test",
                "pw": "$2b$12$seedroundhashdataforinttesting",
                "utype": "candidate",
            },
        ).scalar_one()
        db_session.flush()

        import time as _time
        now = int(_time.time())
        other_identity = IdentityContext(
            user_id=other_user_id, user_type="candidate",
            organization_id=None, admin_role=None,
            token_version=1, issued_at=now, expires_at=now + 3600,
        )

        svc = CodingApiService(db_session)
        with pytest.raises(AuthorizationError):
            svc.submit_code(
                identity=other_identity,
                interview_exchange_id=coding_seed["exchange_id"],
                coding_problem_id=coding_seed["coding_problem_id"],
                language="python3",
                source_code="print(1)",
            )

    def test_admin_can_submit_on_behalf(
        self, db_session, coding_seed, admin_identity,
    ):
        """Admin bypasses candidate ownership check."""
        svc = CodingApiService(db_session)
        result = svc.submit_code(
            identity=admin_identity,
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )
        assert result.execution_status == "pending"


# ====================================================================
# Get Execution Status
# ====================================================================


class TestGetExecutionStatus:
    """Integration tests for CodingApiService.get_execution_status()."""

    def test_get_status_returns_submission_details(
        self, db_session, coding_seed, candidate_identity,
    ):
        """Fetches execution status for an existing submission."""
        svc = CodingApiService(db_session)

        submit_result = svc.submit_code(
            identity=candidate_identity,
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        status = svc.get_execution_status(
            identity=candidate_identity,
            submission_id=submit_result.submission_id,
        )

        assert isinstance(status, ExecutionStatusResponse)
        assert status.submission_id == submit_result.submission_id
        assert status.execution_status == "pending"
        assert status.language == "python3"

    def test_get_status_not_found(
        self, db_session, candidate_identity,
    ):
        """Non-existent submission raises NotFoundError."""
        svc = CodingApiService(db_session)

        with pytest.raises(NotFoundError):
            svc.get_execution_status(
                identity=candidate_identity,
                submission_id=999999,
            )

    def test_hidden_test_case_redaction(
        self, db_session, coding_seed, candidate_identity,
    ):
        """
        Test results for hidden test cases have redacted outputs.

        Seeds test results for both visible + hidden test cases and
        verifies that hidden actual_output is None.
        """
        svc = CodingApiService(db_session)

        # Submit first
        submit_result = svc.submit_code(
            identity=candidate_identity,
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        # Seed execution results manually
        for tc_id in coding_seed["test_case_ids"]:
            db_session.execute(
                text(
                    "INSERT INTO code_execution_results "
                    "(code_submission_id, test_case_id, passed, actual_output) "
                    "VALUES (:sid, :tcid, :passed, :output)"
                ),
                {
                    "sid": submit_result.submission_id,
                    "tcid": tc_id,
                    "passed": True,
                    "output": "25\n",
                },
            )
        db_session.flush()

        status = svc.get_execution_status(
            identity=candidate_identity,
            submission_id=submit_result.submission_id,
        )

        assert len(status.test_results) == 2

        # First test case: visible (is_hidden=False)
        visible_tests = [t for t in status.test_results if t.visible]
        hidden_tests = [t for t in status.test_results if not t.visible]

        assert len(visible_tests) == 1
        assert visible_tests[0].actual_output is not None

        assert len(hidden_tests) == 1
        assert hidden_tests[0].actual_output is None
        assert hidden_tests[0].expected_output is None


# ====================================================================
# List Submissions for Interview
# ====================================================================


class TestListSubmissionsForInterview:
    """Integration tests for CodingApiService.list_submissions_for_interview()."""

    def test_list_returns_submission_summaries(
        self, db_session, coding_seed, candidate_identity, seed_submission,
    ):
        """Returns list of summaries for an interview's submissions."""
        svc = CodingApiService(db_session)

        # Create a submission
        svc.submit_code(
            identity=candidate_identity,
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(1)",
        )

        results = svc.list_submissions_for_interview(
            identity=candidate_identity,
            interview_id=seed_submission,
        )

        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(r, SubmissionSummary) for r in results)
        assert results[0].language == "python3"

    def test_list_empty_interview(
        self, db_session, candidate_identity, seed_submission,
    ):
        """Empty list returned when interview has no submissions."""
        svc = CodingApiService(db_session)

        results = svc.list_submissions_for_interview(
            identity=candidate_identity,
            interview_id=seed_submission,
        )

        assert results == []

    def test_list_wrong_candidate_raises_authorization(
        self, db_session, seed_submission, _unique_suffix,
    ):
        """Wrong candidate is rejected."""
        from app.shared.auth_context import IdentityContext

        other_user_id = db_session.execute(
            text(
                "INSERT INTO users (name, email, password_hash, user_type) "
                "VALUES (:name, :email, :pw, :utype) RETURNING id"
            ),
            {
                "name": "Other Candidate 2",
                "email": f"other2-{_unique_suffix}@seed.test",
                "pw": "$2b$12$seedroundhashdataforinttesting",
                "utype": "candidate",
            },
        ).scalar_one()
        db_session.flush()

        import time as _time
        now = int(_time.time())
        other_identity = IdentityContext(
            user_id=other_user_id, user_type="candidate",
            organization_id=None, admin_role=None,
            token_version=1, issued_at=now, expires_at=now + 3600,
        )

        svc = CodingApiService(db_session)
        with pytest.raises(AuthorizationError):
            svc.list_submissions_for_interview(
                identity=other_identity,
                interview_id=seed_submission,
            )
