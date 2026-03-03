"""
Integration Tests — Proctoring Module End-to-End

Tests the full pipeline: event ingestion → rule application → persistence →
risk computation. Uses mocked DB session and Redis to validate orchestration
without needing live infrastructure.

These tests ensure cross-module wiring is correct:
- IngestionService → RuleEngine → Repository → RiskModelService
- Schema validation → domain logic → persistence → risk computation
"""

import os
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

os.environ["TESTING"] = "1"

from app.proctoring.ingestion.contracts.schemas import (
    ProctoringEventInput,
    BatchEventRequest,
)
from app.proctoring.ingestion.domain.ingestion_service import IngestionService
from app.proctoring.risk_model.domain.risk_computation import (
    EventData,
    compute_risk_score,
    is_flaggable,
)
from app.proctoring.risk_model.domain.risk_service import RiskModelService
from app.proctoring.rules.domain.rule_engine import RuleEngine
from app.proctoring.rules.domain.rule_definitions import (
    ALLOWED_EVENT_TYPES,
    DEFAULT_RULE_MAP,
    DEFAULT_CLUSTERING_MAP,
)
from app.proctoring.persistence.repository import ProctoringEventRepository


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


class FakeRedis:
    """In-memory Redis substitute for integration tests."""

    def __init__(self):
        self._store: dict = {}
        self._sets: dict = {}
        self._hashes: dict = {}
        self._ttls: dict = {}

    def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())

    def sadd(self, key: str, value: str) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        self._sets[key].add(value)
        return 1

    def hset(self, key: str, mapping: dict = None, **kwargs) -> int:
        if mapping:
            self._hashes[key] = {str(k): str(v) for k, v in mapping.items()}
        return 1

    def hgetall(self, key: str) -> dict:
        return self._hashes.get(key, {})

    def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True


class FakeEventModel:
    """Mimics ProctoringEventModel returned by repository."""

    _id_counter = 0

    def __init__(self, **kwargs):
        FakeEventModel._id_counter += 1
        self.id = kwargs.get("id", FakeEventModel._id_counter)
        self.interview_submission_id = kwargs.get("interview_submission_id", 1)
        self.event_type = kwargs.get("event_type", "tab_switch")
        self.severity = kwargs.get("severity", "low")
        self.risk_weight = Decimal(str(kwargs.get("risk_weight", 0.5)))
        self.evidence = kwargs.get("evidence", {})
        self.occurred_at = kwargs.get(
            "occurred_at", datetime(2026, 2, 14, 10, 0, 0, tzinfo=timezone.utc)
        )
        self.created_at = kwargs.get(
            "created_at", datetime(2026, 2, 14, 10, 0, 1, tzinfo=timezone.utc)
        )


@pytest.fixture(autouse=True)
def reset_fake_id_counter():
    FakeEventModel._id_counter = 0
    yield


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.execute = MagicMock(return_value=MagicMock())
    return session


# ════════════════════════════════════════════════════════════════════════
# RuleEngine → RiskComputation Integration
# ════════════════════════════════════════════════════════════════════════


class TestRuleEngineToRiskComputation:
    """Validate that rule engine outputs feed correctly into risk computation."""

    def test_rule_enriched_events_produce_correct_risk(self):
        """Apply rules to 5 tab_switch events, then compute risk score."""
        engine = RuleEngine()
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)

        enriched_events = []
        for i in range(5):
            enriched = engine.apply_rules(
                submission_id=1,
                event_type="tab_switch",
                occurred_at=now + timedelta(seconds=i * 10),
                evidence={},
                recent_count_in_window=i,
                consecutive_count=0,
            )
            enriched_events.append(enriched)

        # Convert enriched events to EventData for risk computation
        event_data = [
            EventData(
                event_id=i + 1,
                event_type=e.event_type,
                risk_weight=e.applied_weight,
                severity=e.applied_severity,
                occurred_at=e.occurred_at,
            )
            for i, e in enumerate(enriched_events)
        ]

        risk = compute_risk_score(
            submission_id=1,
            events=event_data,
            reference_time=now + timedelta(minutes=1),
        )

        # 5 × 0.5 = 2.5 (no clustering triggered, all below threshold=10)
        assert risk.total_risk == 2.5
        assert risk.classification == "low"
        assert risk.event_count == 5
        assert "tab_switch" in risk.breakdown_by_type

    def test_clustering_escalation_affects_risk(self):
        """11 tab_switch events in window → clustering triggered → weight escalated."""
        engine = RuleEngine()
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)

        # Simulate: 11th event triggers clustering (count_in_window >= 10)
        enriched_normal = engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=now,
            evidence={},
            recent_count_in_window=5,
            consecutive_count=0,
        )
        enriched_clustered = engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=now + timedelta(seconds=1),
            evidence={},
            recent_count_in_window=10,  # Triggers clustering
            consecutive_count=0,
        )

        assert enriched_normal.clustering_detected is False
        assert enriched_normal.applied_weight == 0.5
        assert enriched_clustered.clustering_detected is True
        assert enriched_clustered.applied_weight == 0.75  # 0.5 × 1.5

        # Risk from both events
        events = [
            EventData(
                event_id=1,
                event_type="tab_switch",
                risk_weight=enriched_normal.applied_weight,
                severity=enriched_normal.applied_severity,
                occurred_at=now,
            ),
            EventData(
                event_id=2,
                event_type="tab_switch",
                risk_weight=enriched_clustered.applied_weight,
                severity=enriched_clustered.applied_severity,
                occurred_at=now + timedelta(seconds=1),
            ),
        ]
        risk = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=now + timedelta(minutes=1),
        )
        assert risk.total_risk == 1.25  # 0.5 + 0.75

    def test_high_severity_event_flaggable(self):
        """Multiple faces event → high severity → flaggable risk."""
        engine = RuleEngine()
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)

        # 10 multiple_faces events → total weight 30.0 → critical
        events = []
        for i in range(10):
            enriched = engine.apply_rules(
                submission_id=1,
                event_type="multiple_faces",
                occurred_at=now + timedelta(seconds=i),
                evidence={},
                recent_count_in_window=i,
                consecutive_count=0,
            )
            events.append(
                EventData(
                    event_id=i + 1,
                    event_type="multiple_faces",
                    risk_weight=enriched.applied_weight,
                    severity=enriched.applied_severity,
                    occurred_at=now + timedelta(seconds=i),
                )
            )

        risk = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=now + timedelta(minutes=5),
        )

        assert risk.total_risk >= 30.0
        assert risk.classification == "critical"
        assert is_flaggable(risk.classification)


# ════════════════════════════════════════════════════════════════════════
# IngestionService Pipeline (mocked persistence)
# ════════════════════════════════════════════════════════════════════════


class TestIngestionPipeline:
    """Test full ingestion pipeline with mocked DB operations."""

    def _make_event(self, event_type="tab_switch", submission_id=42,
                    ts="2026-02-14T10:30:15.234Z", metadata=None):
        return ProctoringEventInput(
            submission_id=submission_id,
            event_type=event_type,
            timestamp=ts,
            metadata=metadata,
        )

    @patch.object(ProctoringEventRepository, "get_events_in_window", return_value=[])
    @patch.object(ProctoringEventRepository, "get_last_n_events", return_value=[])
    @patch.object(ProctoringEventRepository, "create")
    @patch.object(ProctoringEventRepository, "get_by_submission", return_value=[])
    def test_single_event_accepted(
        self, mock_get_by_sub, mock_create, mock_last_n, mock_window, mock_session, fake_redis,
    ):
        mock_create.return_value = FakeEventModel(
            id=1,
            event_type="tab_switch",
            severity="low",
            risk_weight=0.5,
        )

        service = IngestionService(session=mock_session, redis_client=fake_redis)
        result = service.ingest_event(self._make_event())

        assert result.status == "accepted"
        assert result.event_id == 1
        mock_create.assert_called_once()

    @patch.object(ProctoringEventRepository, "get_events_in_window", return_value=[])
    @patch.object(ProctoringEventRepository, "get_last_n_events", return_value=[])
    @patch.object(ProctoringEventRepository, "create")
    @patch.object(ProctoringEventRepository, "get_by_submission", return_value=[])
    def test_duplicate_event_idempotent(
        self, mock_get_by_sub, mock_create, mock_last_n, mock_window, mock_session, fake_redis,
    ):
        mock_create.return_value = FakeEventModel(id=1, event_type="tab_switch")

        service = IngestionService(session=mock_session, redis_client=fake_redis)
        event = self._make_event()

        # First ingestion
        result1 = service.ingest_event(event)
        assert result1.status == "accepted"

        # Second ingestion: duplicate detected
        result2 = service.ingest_event(event)
        assert result2.status == "duplicate"
        assert result2.event_id is None

    @patch.object(ProctoringEventRepository, "get_events_in_window", return_value=[])
    @patch.object(ProctoringEventRepository, "get_last_n_events", return_value=[])
    @patch.object(ProctoringEventRepository, "create")
    @patch.object(ProctoringEventRepository, "get_by_submission", return_value=[])
    def test_batch_ingestion_all_accepted(
        self, mock_get_by_sub, mock_create, mock_last_n, mock_window, mock_session, fake_redis,
    ):
        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            return FakeEventModel(id=call_count[0], **kwargs)

        mock_create.side_effect = side_effect

        service = IngestionService(session=mock_session, redis_client=fake_redis)
        events = [
            self._make_event(event_type="tab_switch", ts="2026-02-14T10:30:15.234Z"),
            self._make_event(event_type="face_absent", ts="2026-02-14T10:30:16.234Z"),
            self._make_event(event_type="multiple_faces", ts="2026-02-14T10:30:17.234Z"),
        ]
        result = service.ingest_batch(submission_id=42, events=events)

        assert result.accepted == 3
        assert result.rejected == 0
        assert len(result.event_ids) == 3

    @patch.object(ProctoringEventRepository, "get_events_in_window", return_value=[])
    @patch.object(ProctoringEventRepository, "get_last_n_events", return_value=[])
    @patch.object(ProctoringEventRepository, "create")
    @patch.object(ProctoringEventRepository, "get_by_submission", return_value=[])
    def test_batch_submission_id_mismatch_rejected(
        self, mock_get_by_sub, mock_create, mock_last_n, mock_window, mock_session, fake_redis,
    ):
        mock_create.return_value = FakeEventModel(id=1, event_type="tab_switch")

        service = IngestionService(session=mock_session, redis_client=fake_redis)
        events = [
            self._make_event(submission_id=42),
            self._make_event(submission_id=99),  # Mismatch!
        ]
        result = service.ingest_batch(submission_id=42, events=events)

        assert result.accepted == 1
        assert result.rejected == 1
        assert result.errors is not None
        assert "mismatch" in result.errors[0]["reason"]


# ════════════════════════════════════════════════════════════════════════
# RiskModelService with mocked persistence
# ════════════════════════════════════════════════════════════════════════


class TestRiskModelServiceIntegration:
    """Test RiskModelService orchestration with mocked DB."""

    @patch.object(ProctoringEventRepository, "get_by_submission")
    def test_compute_returns_valid_risk(self, mock_get_events, mock_session, fake_redis):
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_get_events.return_value = [
            FakeEventModel(id=1, event_type="tab_switch", severity="low", risk_weight=0.5, occurred_at=now),
            FakeEventModel(id=2, event_type="face_absent", severity="medium", risk_weight=1.5, occurred_at=now),
        ]

        service = RiskModelService(session=mock_session, redis_client=fake_redis)
        risk = service.compute(submission_id=42)

        assert risk.total_risk == 2.0
        assert risk.classification == "low"
        assert risk.event_count == 2
        assert risk.submission_id == 42

    @patch.object(ProctoringEventRepository, "get_by_submission")
    def test_compute_caches_in_redis(self, mock_get_events, mock_session, fake_redis):
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_get_events.return_value = [
            FakeEventModel(id=1, event_type="tab_switch", severity="low", risk_weight=0.5, occurred_at=now),
        ]

        service = RiskModelService(session=mock_session, redis_client=fake_redis)
        risk = service.compute(submission_id=42)

        cached = fake_redis.hgetall("proctoring:risk:42")
        assert cached["total_risk"] == str(risk.total_risk)
        assert cached["classification"] == "low"
        assert cached["event_count"] == str(risk.event_count)

    @patch.object(ProctoringEventRepository, "get_by_submission")
    def test_compute_updates_submission_record(self, mock_get_events, mock_session, fake_redis):
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_get_events.return_value = [
            FakeEventModel(id=1, event_type="multiple_faces", severity="high", risk_weight=3.0, occurred_at=now),
        ] * 10  # 10 × 3.0 = 30.0 → critical

        service = RiskModelService(session=mock_session, redis_client=fake_redis)
        risk = service.compute(submission_id=42)

        assert risk.classification == "critical"
        # Verify session.execute was called for the UPDATE statement
        mock_session.execute.assert_called()

    @patch.object(ProctoringEventRepository, "get_by_submission")
    def test_compute_with_no_events(self, mock_get_events, mock_session, fake_redis):
        mock_get_events.return_value = []

        service = RiskModelService(session=mock_session, redis_client=fake_redis)
        risk = service.compute(submission_id=99)

        assert risk.total_risk == 0.0
        assert risk.classification == "low"
        assert risk.event_count == 0

    @patch.object(ProctoringEventRepository, "get_by_submission")
    def test_compute_without_redis_graceful(self, mock_get_events, mock_session):
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_get_events.return_value = [
            FakeEventModel(id=1, event_type="tab_switch", severity="low", risk_weight=0.5, occurred_at=now),
        ]

        service = RiskModelService(session=mock_session, redis_client=None)
        risk = service.compute(submission_id=42)

        assert risk.total_risk == 0.5
        assert risk.classification == "low"

    @patch.object(ProctoringEventRepository, "get_by_submission")
    def test_get_cached_risk_returns_cached_data(self, mock_get_events, mock_session, fake_redis):
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_get_events.return_value = [
            FakeEventModel(id=1, event_type="tab_switch", severity="low", risk_weight=0.5, occurred_at=now),
        ]

        service = RiskModelService(session=mock_session, redis_client=fake_redis)
        service.compute(submission_id=42)
        cached = service.get_cached_risk(submission_id=42)

        assert cached is not None
        assert cached["total_risk"] == 0.5
        assert cached["classification"] == "low"

    def test_get_cached_risk_returns_none_without_redis(self, mock_session):
        service = RiskModelService(session=mock_session, redis_client=None)
        cached = service.get_cached_risk(submission_id=42)
        assert cached is None


# ════════════════════════════════════════════════════════════════════════
# Cross-Module Contract Validation
# ════════════════════════════════════════════════════════════════════════


class TestCrossModuleContracts:
    """Validate that module boundaries and contracts are respected."""

    def test_all_event_types_have_rules(self):
        """Every allowed event type must have a corresponding rule."""
        for event_type in ALLOWED_EVENT_TYPES:
            assert event_type in DEFAULT_RULE_MAP, (
                f"Event type '{event_type}' has no rule in DEFAULT_RULE_MAP"
            )

    def test_rule_severities_are_db_compatible(self):
        """Rule severities must be valid PostgreSQL enum values."""
        valid_db_severities = {"low", "medium", "high", "critical"}
        for rule in DEFAULT_RULE_MAP.values():
            assert rule.base_severity in valid_db_severities, (
                f"Rule '{rule.event_type}' has severity '{rule.base_severity}' "
                f"not in DB enum: {valid_db_severities}"
            )

    def test_clustering_rules_reference_valid_event_types(self):
        """Clustering rules must reference known event types."""
        for event_type, rules in DEFAULT_CLUSTERING_MAP.items():
            assert event_type in ALLOWED_EVENT_TYPES, (
                f"Clustering rule for '{event_type}' references unknown event type"
            )
            for rule in rules:
                assert rule.condition_type in ("count_in_window", "consecutive"), (
                    f"Invalid clustering condition: {rule.condition_type}"
                )
                assert rule.threshold > 0
                assert rule.weight_multiplier > 0

    def test_risk_computation_dto_from_rule_engine(self):
        """Validate that rule engine output can be consumed by risk computation."""
        engine = RuleEngine()
        now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)
        enriched = engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=now,
            evidence={},
        )

        # Must be convertible to EventData for risk computation
        event_data = EventData(
            event_id=1,
            event_type=enriched.event_type,
            risk_weight=enriched.applied_weight,
            severity=enriched.applied_severity,
            occurred_at=enriched.occurred_at,
        )
        assert event_data.event_type == "tab_switch"
        assert event_data.risk_weight == 0.5
