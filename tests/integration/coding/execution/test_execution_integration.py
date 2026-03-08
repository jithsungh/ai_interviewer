"""
Integration tests for the coding/execution module — persistence layer.

These tests hit a real PostgreSQL database to validate:
- Repository CRUD operations and query correctness
- UNIQUE constraint enforcement
- SELECT ... FOR UPDATE locking behaviour
- Status update + score persistence
- Full execution service integration (with mocked sandbox)

Requires:
- PostgreSQL with interviewer schema + coding execution migration applied
- Set TEST_DATABASE_URL env-var to override the default test-cluster address

Each test runs within a transactional session that is **always rolled back**
so no data leaks across tests.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.exc import IntegrityError

from app.coding.enums import ExecutionStatus
from app.coding.enums import TestCaseStatus as _TCStatus
from app.coding.execution.contracts import (
    ExecuteSubmissionCommand,
    SubmissionData,
)
from app.coding.execution.contracts import TestCase as _TC
from app.coding.execution.service import ExecutionService
from app.coding.persistence.repositories import (
    SqlCodeExecutionResultRepository,
    SqlCodeSubmissionRepository,
)
from app.coding.sandbox.contracts import SandboxExecutionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sandbox_result(
    stdout: str = "25\n",
    stderr: str = "",
    exit_code: int = 0,
    runtime_ms: int = 150,
    memory_kb: int = 8192,
    timed_out: bool = False,
    memory_exceeded: bool = False,
    compilation_output: str = "",
) -> SandboxExecutionResult:
    return SandboxExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        runtime_ms=runtime_ms,
        memory_kb=memory_kb,
        timed_out=timed_out,
        memory_exceeded=memory_exceeded,
        compilation_output=compilation_output,
    )


# ====================================================================
# CodeSubmissionRepository — CRUD + constraints
# ====================================================================


class TestCodeSubmissionRepositoryCRUD:
    """Verify core CRUD operations against a real database."""

    def test_create_and_get_by_id(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        entity = repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        assert entity.id is not None
        assert entity.execution_status == "pending"
        assert entity.language == "python3"

        fetched = repo.get_by_id(entity.id)
        assert fetched is not None
        assert fetched.id == entity.id
        assert fetched.source_code == "print(int(input())**2)"

    def test_get_by_exchange_id(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        created = repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        found = repo.get_by_exchange_id(coding_seed["exchange_id"])
        assert found is not None
        assert found.id == created.id

    def test_get_by_exchange_id_not_found(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        found = repo.get_by_exchange_id(999999)
        assert found is None

    def test_get_by_id_not_found(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        found = repo.get_by_id(999999)
        assert found is None

    def test_get_for_update(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        created = repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        locked = repo.get_for_update(created.id)
        assert locked is not None
        assert locked.id == created.id

    def test_update_status(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        created = repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        repo.update_status(
            created.id,
            "running",
        )

        updated = repo.get_by_id(created.id)
        assert updated is not None
        assert updated.execution_status == "running"

    def test_update_status_with_score(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        created = repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        now = datetime.now(timezone.utc)
        repo.update_status(
            created.id,
            "passed",
            score=100.0,
            execution_time_ms=300,
            memory_kb=16384,
            executed_at=now,
        )

        updated = repo.get_by_id(created.id)
        assert updated is not None
        assert updated.execution_status == "passed"
        assert float(updated.score) == 100.0
        assert updated.execution_time_ms == 300
        assert updated.memory_kb == 16384

    def test_list_pending(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        created = repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        pending = repo.list_pending(limit=10000)
        assert any(s.id == created.id for s in pending)

    def test_count_submissions_since(self, db_session, coding_seed):
        repo = SqlCodeSubmissionRepository(db_session)

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        count = repo.count_submissions_since(
            coding_seed["exchange_id"], one_hour_ago
        )
        assert count >= 1


class TestCodeSubmissionRepositoryConstraints:
    """Verify database-enforced constraints."""

    def test_duplicate_exchange_id_raises(self, db_session, coding_seed):
        """UNIQUE constraint on interview_exchange_id prevents duplicates."""
        repo = SqlCodeSubmissionRepository(db_session)

        repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="first",
        )

        with pytest.raises(IntegrityError):
            repo.create(
                interview_exchange_id=coding_seed["exchange_id"],
                coding_problem_id=coding_seed["coding_problem_id"],
                language="python3",
                source_code="second",
            )


# ====================================================================
# CodeExecutionResultRepository — CRUD + constraints
# ====================================================================


class TestCodeExecutionResultRepositoryCRUD:
    """Verify execution result persistence."""

    def test_create_and_get_by_submission(self, db_session, coding_seed):
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        result = res_repo.create(
            code_submission_id=submission.id,
            test_case_id=coding_seed["test_case_ids"][0],
            passed=True,
            actual_output="25\n",
            runtime_ms=150,
            memory_kb=8192,
            exit_code=0,
            runtime_output="",
            feedback="Passed",
        )

        assert result.id is not None
        assert result.passed is True

        results = res_repo.get_by_submission(submission.id)
        assert len(results) == 1
        assert results[0].test_case_id == coding_seed["test_case_ids"][0]

    def test_get_by_submission_and_test(self, db_session, coding_seed):
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        res_repo.create(
            code_submission_id=submission.id,
            test_case_id=coding_seed["test_case_ids"][0],
            passed=True,
            actual_output="25\n",
            runtime_ms=150,
            memory_kb=8192,
            exit_code=0,
            runtime_output="",
            feedback="Passed",
        )

        found = res_repo.get_by_submission_and_test(
            submission.id, coding_seed["test_case_ids"][0]
        )
        assert found is not None
        assert found.passed is True

    def test_exists(self, db_session, coding_seed):
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        assert res_repo.exists(submission.id, coding_seed["test_case_ids"][0]) is False

        res_repo.create(
            code_submission_id=submission.id,
            test_case_id=coding_seed["test_case_ids"][0],
            passed=True,
            actual_output="25\n",
            runtime_ms=100,
            memory_kb=4096,
            exit_code=0,
            runtime_output="",
            feedback="Passed",
        )

        assert res_repo.exists(submission.id, coding_seed["test_case_ids"][0]) is True

    def test_multiple_test_cases_ordered(self, db_session, coding_seed):
        """Results are returned ordered by test_case_id ASC."""
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        # Insert in reverse order
        for tc_id in reversed(coding_seed["test_case_ids"]):
            res_repo.create(
                code_submission_id=submission.id,
                test_case_id=tc_id,
                passed=True,
                actual_output="ok",
                runtime_ms=100,
                memory_kb=4096,
                exit_code=0,
                runtime_output="",
                feedback="Passed",
            )

        results = res_repo.get_by_submission(submission.id)
        assert len(results) == 2
        assert results[0].test_case_id < results[1].test_case_id


class TestCodeExecutionResultConstraints:
    """Verify result-level constraints."""

    def test_duplicate_submission_test_case_raises(self, db_session, coding_seed):
        """UNIQUE(code_submission_id, test_case_id) constraint."""
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )

        tc_id = coding_seed["test_case_ids"][0]

        res_repo.create(
            code_submission_id=submission.id,
            test_case_id=tc_id,
            passed=True,
            actual_output="25\n",
            runtime_ms=100,
            memory_kb=4096,
            exit_code=0,
            runtime_output="",
            feedback="Passed",
        )

        with pytest.raises(IntegrityError):
            res_repo.create(
                code_submission_id=submission.id,
                test_case_id=tc_id,
                passed=False,
                actual_output="WRONG",
                runtime_ms=200,
                memory_kb=8192,
                exit_code=1,
                runtime_output="error",
                feedback="Failed",
            )


# ====================================================================
# ExecutionService — end-to-end with real DB + mocked sandbox
# ====================================================================


class TestExecutionServiceIntegration:
    """
    Full execution lifecycle against a real database.

    The sandbox is mocked (no Docker required) but all repository
    operations hit PostgreSQL.
    """

    def test_full_execution_happy_path(self, db_session, coding_seed):
        """Execute a submission against two test cases — all pass."""
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        # Pre-create a pending submission
        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        sandbox = MagicMock()
        sandbox.execute.side_effect = [
            _make_sandbox_result(stdout="25\n"),
            _make_sandbox_result(stdout="9\n"),
        ]

        service = ExecutionService(
            submission_repo=sub_repo,
            result_repo=res_repo,
            sandbox_executor=sandbox,
        )

        command = ExecuteSubmissionCommand(
            submission_id=submission.id,
            submission_data=SubmissionData(
                language="python3",
                source_code="print(int(input())**2)",
                coding_problem_id=coding_seed["coding_problem_id"],
            ),
            test_cases=[
                _TC(
                    test_case_id=coding_seed["test_case_ids"][0],
                    input_data="5\n",
                    expected_output="25\n",
                    weight=1.0,
                    time_limit_ms=2000,
                    memory_limit_kb=262144,
                    is_hidden=False,
                ),
                _TC(
                    test_case_id=coding_seed["test_case_ids"][1],
                    input_data="3\n",
                    expected_output="9\n",
                    weight=1.0,
                    time_limit_ms=2000,
                    memory_limit_kb=262144,
                    is_hidden=False,
                ),
            ],
        )

        result = service.execute(command)

        # Verify returned result
        assert result.execution_status == ExecutionStatus.PASSED
        assert result.score == 100.0
        assert len(result.test_results) == 2
        assert all(r.passed for r in result.test_results)

        # Verify DB state
        persisted = sub_repo.get_by_id(submission.id)
        assert persisted is not None
        assert persisted.execution_status == "passed"
        assert float(persisted.score) == 100.0

        db_results = res_repo.get_by_submission(submission.id)
        assert len(db_results) == 2

    def test_full_execution_partial_failure(self, db_session, coding_seed):
        """One test passes, one fails — verify partial score in DB."""
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="print(int(input())**2)",
        )

        sandbox = MagicMock()
        sandbox.execute.side_effect = [
            _make_sandbox_result(stdout="25\n"),   # correct
            _make_sandbox_result(stdout="10\n"),   # wrong
        ]

        service = ExecutionService(
            submission_repo=sub_repo,
            result_repo=res_repo,
            sandbox_executor=sandbox,
        )

        command = ExecuteSubmissionCommand(
            submission_id=submission.id,
            submission_data=SubmissionData(
                language="python3",
                source_code="print(int(input())**2)",
                coding_problem_id=coding_seed["coding_problem_id"],
            ),
            test_cases=[
                _TC(
                    test_case_id=coding_seed["test_case_ids"][0],
                    input_data="5\n",
                    expected_output="25\n",
                    weight=1.0,
                    time_limit_ms=2000,
                    memory_limit_kb=262144,
                    is_hidden=False,
                ),
                _TC(
                    test_case_id=coding_seed["test_case_ids"][1],
                    input_data="3\n",
                    expected_output="9\n",
                    weight=1.0,
                    time_limit_ms=2000,
                    memory_limit_kb=262144,
                    is_hidden=False,
                ),
            ],
        )

        result = service.execute(command)

        assert result.execution_status == ExecutionStatus.FAILED
        assert result.score == 50.0
        assert result.test_results[0].passed is True
        assert result.test_results[1].passed is False

        persisted = sub_repo.get_by_id(submission.id)
        assert persisted is not None
        assert persisted.execution_status == "failed"
        assert float(persisted.score) == 50.0

    def test_already_terminal_returns_error(self, db_session, coding_seed):
        """Executing an already-finalized submission returns error."""
        sub_repo = SqlCodeSubmissionRepository(db_session)
        res_repo = SqlCodeExecutionResultRepository(db_session)

        submission = sub_repo.create(
            interview_exchange_id=coding_seed["exchange_id"],
            coding_problem_id=coding_seed["coding_problem_id"],
            language="python3",
            source_code="x = 1",
        )
        # Force to terminal state
        sub_repo.update_status(submission.id, "passed", score=100.0)

        sandbox = MagicMock()
        service = ExecutionService(
            submission_repo=sub_repo,
            result_repo=res_repo,
            sandbox_executor=sandbox,
        )

        command = ExecuteSubmissionCommand(
            submission_id=submission.id,
            submission_data=SubmissionData(
                language="python3",
                source_code="x = 1",
                coding_problem_id=coding_seed["coding_problem_id"],
            ),
            test_cases=[
                _TC(
                    test_case_id=coding_seed["test_case_ids"][0],
                    input_data="5\n",
                    expected_output="25\n",
                    weight=1.0,
                    time_limit_ms=2000,
                    memory_limit_kb=262144,
                    is_hidden=False,
                ),
            ],
        )

        result = service.execute(command)

        assert result.execution_status == ExecutionStatus.ERROR
        sandbox.execute.assert_not_called()
