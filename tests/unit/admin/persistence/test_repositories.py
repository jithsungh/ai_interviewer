"""
Unit Tests for Admin Persistence Repositories

Tests repository classes using a mocked SQLAlchemy Session.
Validates:
  • Correct model classes are queried
  • Mapper functions are invoked
  • Pagination, filtering, and multi-tenancy logic
  • Override routing by ContentType
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from app.admin.domain.entities import (
    SUPER_ORG_ID,
    CodingProblem,
    CodingTopic,
    CodingTopicType,
    ContentType,
    DifficultyLevel,
    InterviewScope,
    OverrideRecord,
    Question,
    QuestionType,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRole,
    TemplateRubric,
    TemplateScope,
    Topic,
    Window,
    WindowRoleTemplate,
)
from app.admin.persistence.models import (
    AuditLogModel,
    CodingProblemModel,
    CodingProblemOverrideModel,
    CodingTopicModel,
    InterviewSubmissionModel,
    InterviewSubmissionWindowModel,
    InterviewTemplateModel,
    InterviewTemplateRoleModel,
    InterviewTemplateRubricModel,
    OVERRIDE_MODEL_MAP,
    QuestionModel,
    QuestionOverrideModel,
    RoleModel,
    RoleOverrideModel,
    RubricDimensionModel,
    RubricModel,
    RubricOverrideModel,
    TemplateOverrideModel,
    TopicModel,
    TopicOverrideModel,
    WindowRoleTemplateModel,
)
from app.admin.persistence.repositories import (
    SqlAuditLogRepository,
    SqlCodingProblemRepository,
    SqlOverrideRepository,
    SqlQuestionRepository,
    SqlRoleRepository,
    SqlRubricRepository,
    SqlSubmissionRepository,
    SqlTemplateRepository,
    SqlTopicRepository,
    SqlWindowRepository,
)


NOW = datetime(2026, 2, 27, 12, 0, 0, tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────
# Helper: mock session that returns chainable query objects
# ─────────────────────────────────────────────────────────────────────────

def _make_session() -> MagicMock:
    """
    Produce a mock Session whose .query() returns a chainable mock
    (filter → order_by → offset → limit → all/scalar/first).
    """
    session = MagicMock(spec_set=[
        "get", "query", "add", "flush", "delete",
    ])
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.offset.return_value = chain
    chain.limit.return_value = chain
    chain.all.return_value = []
    chain.scalar.return_value = 0
    chain.first.return_value = None
    chain.delete.return_value = 0
    chain.update.return_value = 0
    chain.subquery.return_value = MagicMock()
    session.query.return_value = chain
    return session


def _template_model(tid: int = 10) -> InterviewTemplateModel:
    m = InterviewTemplateModel()
    m.id = tid
    m.name = "T"
    m.description = None
    m.scope = "public"
    m.organization_id = None
    m.template_structure = {}
    m.rules = None
    m.total_estimated_time_minutes = None
    m.version = 1
    m.is_active = True
    m.created_at = NOW
    m.updated_at = NOW
    return m


# ═══════════════════════════════════════════════════════════════════════════
# Template Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlTemplateRepository:
    def test_get_by_id_found(self):
        session = _make_session()
        model = _template_model()
        session.get.return_value = model
        repo = SqlTemplateRepository(session)
        result = repo.get_by_id(10)
        session.get.assert_called_once_with(InterviewTemplateModel, 10)
        assert isinstance(result, Template)
        assert result.id == 10

    def test_get_by_id_not_found(self):
        session = _make_session()
        session.get.return_value = None
        repo = SqlTemplateRepository(session)
        assert repo.get_by_id(999) is None

    def test_list_for_organization_calls_filter_and_paginate(self):
        session = _make_session()
        m = _template_model()
        chain = session.query.return_value
        chain.all.return_value = [m]
        repo = SqlTemplateRepository(session)
        result = repo.list_for_organization(5, page=2, per_page=10)
        assert len(result) == 1
        assert isinstance(result[0], Template)
        # Query is called with the model
        session.query.assert_called_once_with(InterviewTemplateModel)

    def test_list_for_organization_active_filter(self):
        session = _make_session()
        chain = session.query.return_value
        repo = SqlTemplateRepository(session)
        repo.list_for_organization(5, is_active=True)
        # filter should be called at least twice (org filter + is_active)
        assert chain.filter.call_count >= 2

    def test_count_for_organization(self):
        session = _make_session()
        chain = session.query.return_value
        chain.scalar.return_value = 42
        repo = SqlTemplateRepository(session)
        assert repo.count_for_organization(5) == 42

    def test_create_flushes_and_returns_entity(self):
        session = _make_session()
        repo = SqlTemplateRepository(session)
        t = Template(
            id=None, name="New", description=None,
            scope=TemplateScope.PUBLIC, organization_id=None,
            template_structure={},
        )
        # We need to patch the mapper to actually test the flow
        with patch("app.admin.persistence.repositories.template_entity_to_model") as mock_to_model, \
             patch("app.admin.persistence.repositories.template_model_to_entity") as mock_to_entity:
            mock_model = _template_model()
            mock_to_model.return_value = mock_model
            mock_to_entity.return_value = t
            result = repo.create(t)
            session.add.assert_called_once_with(mock_model)
            session.flush.assert_called_once()

    def test_update_gets_existing_model(self):
        session = _make_session()
        existing = _template_model()
        session.get.return_value = existing
        repo = SqlTemplateRepository(session)
        t = Template(
            id=10, name="Updated", description=None,
            scope=TemplateScope.PUBLIC, organization_id=None,
            template_structure={},
        )
        result = repo.update(t)
        session.get.assert_called_once_with(InterviewTemplateModel, 10)
        session.flush.assert_called_once()

    def test_exists_with_name_true(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = (1,)
        repo = SqlTemplateRepository(session)
        assert repo.exists_with_name("T", None) is True

    def test_exists_with_name_false(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlTemplateRepository(session)
        assert repo.exists_with_name("T", None) is False

    def test_exists_with_name_exclude_id(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlTemplateRepository(session)
        repo.exists_with_name("T", None, exclude_id=10)
        # filter called: (name, org_id) then (exclude_id)
        assert chain.filter.call_count == 2

    def test_get_latest_version(self):
        session = _make_session()
        chain = session.query.return_value
        chain.scalar.return_value = 5
        repo = SqlTemplateRepository(session)
        assert repo.get_latest_version("T", 1) == 5

    def test_get_latest_version_none(self):
        session = _make_session()
        chain = session.query.return_value
        chain.scalar.return_value = None
        repo = SqlTemplateRepository(session)
        assert repo.get_latest_version("T", 1) is None

    def test_set_template_roles_deletes_and_inserts(self):
        session = _make_session()
        repo = SqlTemplateRepository(session)
        repo.set_template_roles(10, [1, 2, 3])
        # delete old
        chain = session.query.return_value
        chain.delete.assert_called_once()
        # add 3 new
        assert session.add.call_count == 3
        session.flush.assert_called()

    def test_get_template_roles(self):
        session = _make_session()
        chain = session.query.return_value
        m = InterviewTemplateRoleModel()
        m.interview_template_id = 10
        m.role_id = 1
        chain.all.return_value = [m]
        repo = SqlTemplateRepository(session)
        roles = repo.get_template_roles(10)
        assert len(roles) == 1
        assert isinstance(roles[0], TemplateRole)

    def test_set_template_rubrics(self):
        session = _make_session()
        repo = SqlTemplateRepository(session)
        rubrics = [
            TemplateRubric(id=None, interview_template_id=10, rubric_id=1, section_name="A"),
            TemplateRubric(id=None, interview_template_id=10, rubric_id=2, section_name="B"),
        ]
        repo.set_template_rubrics(10, rubrics)
        chain = session.query.return_value
        chain.delete.assert_called_once()
        assert session.add.call_count == 2

    def test_get_template_rubrics(self):
        session = _make_session()
        chain = session.query.return_value
        m = InterviewTemplateRubricModel()
        m.id = 1
        m.interview_template_id = 10
        m.rubric_id = 5
        m.section_name = "X"
        chain.all.return_value = [m]
        repo = SqlTemplateRepository(session)
        rubrics = repo.get_template_rubrics(10)
        assert len(rubrics) == 1
        assert isinstance(rubrics[0], TemplateRubric)


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlRubricRepository:
    def test_get_by_id(self):
        session = _make_session()
        m = RubricModel()
        m.id = 20
        m.organization_id = None
        m.name = "R"
        m.description = None
        m.scope = "public"
        m.schema = None
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        session.get.return_value = m
        repo = SqlRubricRepository(session)
        result = repo.get_by_id(20)
        assert isinstance(result, Rubric)

    def test_get_by_id_not_found(self):
        session = _make_session()
        session.get.return_value = None
        repo = SqlRubricRepository(session)
        assert repo.get_by_id(999) is None

    def test_set_dimensions_replaces(self):
        session = _make_session()
        repo = SqlRubricRepository(session)
        dims = [
            RubricDimension(
                id=None, rubric_id=20, dimension_name="D1",
                description=None, max_score=Decimal("10"), weight=Decimal("1.0"),
            ),
        ]
        repo.set_dimensions(20, dims)
        chain = session.query.return_value
        chain.delete.assert_called_once()
        assert session.add.call_count == 1

    def test_get_dimensions(self):
        session = _make_session()
        chain = session.query.return_value
        m = RubricDimensionModel()
        m.id = 1
        m.rubric_id = 20
        m.dimension_name = "PS"
        m.description = None
        m.max_score = 10.0
        m.weight = 1.0
        m.criteria = None
        m.sequence_order = 0
        chain.all.return_value = [m]
        repo = SqlRubricRepository(session)
        dims = repo.get_dimensions(20)
        assert len(dims) == 1
        assert isinstance(dims[0], RubricDimension)


# ═══════════════════════════════════════════════════════════════════════════
# Role Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlRoleRepository:
    def test_get_by_id(self):
        session = _make_session()
        m = RoleModel()
        m.id = 1
        m.name = "SE"
        m.description = None
        m.scope = "public"
        m.organization_id = None
        session.get.return_value = m
        repo = SqlRoleRepository(session)
        assert isinstance(repo.get_by_id(1), Role)

    def test_count_for_organization(self):
        session = _make_session()
        chain = session.query.return_value
        chain.scalar.return_value = 7
        repo = SqlRoleRepository(session)
        assert repo.count_for_organization(5) == 7

    def test_exists_with_name(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlRoleRepository(session)
        assert repo.exists_with_name("X", 5) is False


# ═══════════════════════════════════════════════════════════════════════════
# Topic Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlTopicRepository:
    def test_get_topic_by_id(self):
        session = _make_session()
        m = TopicModel()
        m.id = 1
        m.name = "Algo"
        m.description = None
        m.parent_topic_id = None
        m.scope = "public"
        m.organization_id = None
        m.estimated_time_minutes = None
        m.created_at = NOW
        m.updated_at = NOW
        session.get.return_value = m
        repo = SqlTopicRepository(session)
        result = repo.get_topic_by_id(1)
        assert isinstance(result, Topic)

    def test_get_topic_ancestors_no_parent(self):
        session = _make_session()
        m = TopicModel()
        m.id = 1
        m.parent_topic_id = None
        session.get.return_value = m
        repo = SqlTopicRepository(session)
        assert repo.get_topic_ancestors(1) == []

    def test_get_topic_ancestors_chain(self):
        """Simulates a chain: 3 → 2 → 1 (root)."""
        session = _make_session()
        m1 = TopicModel()
        m1.id = 1
        m1.parent_topic_id = None

        m2 = TopicModel()
        m2.id = 2
        m2.parent_topic_id = 1

        m3 = TopicModel()
        m3.id = 3
        m3.parent_topic_id = 2

        def get_side_effect(cls, tid):
            return {1: m1, 2: m2, 3: m3}.get(tid)

        session.get.side_effect = get_side_effect
        repo = SqlTopicRepository(session)
        ancestors = repo.get_topic_ancestors(3)
        assert ancestors == [2, 1]

    def test_get_coding_topic_by_id(self):
        session = _make_session()
        m = CodingTopicModel()
        m.id = 10
        m.name = "Trees"
        m.description = None
        m.topic_type = "data_structure"
        m.parent_topic_id = None
        m.scope = "public"
        m.organization_id = None
        m.display_order = 0
        m.created_at = NOW
        m.updated_at = NOW
        session.get.return_value = m
        repo = SqlTopicRepository(session)
        result = repo.get_coding_topic_by_id(10)
        assert isinstance(result, CodingTopic)


# ═══════════════════════════════════════════════════════════════════════════
# Question Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlQuestionRepository:
    def test_get_by_id(self):
        session = _make_session()
        m = QuestionModel()
        m.id = 100
        m.question_text = "Q"
        m.answer_text = None
        m.question_type = "behavioral"
        m.difficulty = "easy"
        m.scope = "public"
        m.organization_id = None
        m.source_type = None
        m.estimated_time_minutes = 5
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        session.get.return_value = m
        repo = SqlQuestionRepository(session)
        result = repo.get_by_id(100)
        assert isinstance(result, Question)

    def test_list_for_organization_with_type_filter(self):
        session = _make_session()
        chain = session.query.return_value
        repo = SqlQuestionRepository(session)
        repo.list_for_organization(5, question_type="technical")
        # org filter + type filter = at least 2 filter calls
        assert chain.filter.call_count >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Coding Problem Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlCodingProblemRepository:
    def test_get_by_id(self):
        session = _make_session()
        m = CodingProblemModel()
        m.id = 200
        m.title = "Two Sum"
        m.body = "body"
        m.difficulty = "easy"
        m.scope = "public"
        m.organization_id = None
        m.description = None
        m.constraints = None
        m.estimated_time_minutes = 30
        m.is_active = True
        m.source_name = None
        m.source_id = None
        m.source_slug = None
        m.raw_content = None
        m.examples = []
        m.constraints_structured = []
        m.hints = []
        m.stats = None
        m.code_snippets = {}
        m.created_at = NOW
        m.updated_at = NOW
        session.get.return_value = m
        repo = SqlCodingProblemRepository(session)
        result = repo.get_by_id(200)
        assert isinstance(result, CodingProblem)


# ═══════════════════════════════════════════════════════════════════════════
# Window Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlWindowRepository:
    def _make_window_model(self) -> InterviewSubmissionWindowModel:
        m = InterviewSubmissionWindowModel()
        m.id = 50
        m.organization_id = 5
        m.admin_id = 1
        m.name = "W"
        m.scope = "global"
        m.start_time = NOW
        m.end_time = datetime(2026, 3, 27, tzinfo=timezone.utc)
        m.timezone = "UTC"
        m.max_allowed_submissions = None
        m.allow_after_end_time = False
        m.allow_resubmission = False
        return m

    def test_get_by_id(self):
        session = _make_session()
        session.get.return_value = self._make_window_model()
        repo = SqlWindowRepository(session)
        result = repo.get_by_id(50)
        assert isinstance(result, Window)
        assert result.scope == InterviewScope.GLOBAL

    def test_find_overlapping_windows_calls_subquery(self):
        session = _make_session()
        chain = session.query.return_value
        chain.all.return_value = []
        repo = SqlWindowRepository(session)
        result = repo.find_overlapping_windows(
            5, 1, NOW, datetime(2026, 3, 27, tzinfo=timezone.utc),
        )
        assert result == []
        # First query is the subquery, second is the main query
        assert session.query.call_count >= 2

    def test_set_mappings(self):
        session = _make_session()
        repo = SqlWindowRepository(session)
        mappings = [
            WindowRoleTemplate(id=None, window_id=50, role_id=1, template_id=10),
            WindowRoleTemplate(id=None, window_id=50, role_id=2, template_id=20),
        ]
        repo.set_mappings(50, mappings)
        chain = session.query.return_value
        chain.delete.assert_called_once()
        assert session.add.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# Submission Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlSubmissionRepository:
    def test_template_is_in_use_true(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = (1,)
        repo = SqlSubmissionRepository(session)
        assert repo.template_is_in_use(10) is True

    def test_template_is_in_use_false(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlSubmissionRepository(session)
        assert repo.template_is_in_use(10) is False

    def test_role_is_in_use(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlSubmissionRepository(session)
        assert repo.role_is_in_use(1) is False

    def test_window_has_submissions(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlSubmissionRepository(session)
        assert repo.window_has_submissions(50) is False


# ═══════════════════════════════════════════════════════════════════════════
# Override Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlOverrideRepository:
    def test_get_override_found(self):
        session = _make_session()
        chain = session.query.return_value
        m = TemplateOverrideModel()
        m.id = 1
        m.organization_id = 5
        m.base_content_id = 10
        m.override_fields = {"name": "Custom"}
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        chain.first.return_value = m
        repo = SqlOverrideRepository(session)
        result = repo.get_override(5, 10, ContentType.TEMPLATE)
        assert isinstance(result, OverrideRecord)
        assert result.override_fields == {"name": "Custom"}

    def test_get_override_not_found(self):
        session = _make_session()
        chain = session.query.return_value
        chain.first.return_value = None
        repo = SqlOverrideRepository(session)
        assert repo.get_override(5, 10, ContentType.TEMPLATE) is None

    def test_create_override(self):
        session = _make_session()
        repo = SqlOverrideRepository(session)
        override = OverrideRecord(
            id=None, organization_id=5, base_content_id=10,
            content_type=ContentType.RUBRIC, override_fields={"name": "X"},
        )
        with patch("app.admin.persistence.repositories.override_entity_to_model") as mock_to_model, \
             patch("app.admin.persistence.repositories.override_model_to_entity") as mock_to_entity:
            mock_model = RubricOverrideModel()
            mock_to_model.return_value = mock_model
            mock_to_entity.return_value = override
            repo.create_override(override)
            session.add.assert_called_once_with(mock_model)
            session.flush.assert_called_once()

    def test_delete_override_returns_true(self):
        session = _make_session()
        chain = session.query.return_value
        chain.delete.return_value = 1
        repo = SqlOverrideRepository(session)
        assert repo.delete_override(5, 10, ContentType.TOPIC) is True

    def test_delete_override_returns_false(self):
        session = _make_session()
        chain = session.query.return_value
        chain.delete.return_value = 0
        repo = SqlOverrideRepository(session)
        assert repo.delete_override(5, 10, ContentType.TOPIC) is False

    def test_mark_overrides_stale(self):
        session = _make_session()
        chain = session.query.return_value
        chain.update.return_value = 3
        repo = SqlOverrideRepository(session)
        count = repo.mark_overrides_stale(10, ContentType.QUESTION)
        assert count == 3
        chain.update.assert_called_once()

    @pytest.mark.parametrize("content_type", list(ContentType))
    def test_model_cls_resolves_for_all_types(self, content_type: ContentType):
        session = _make_session()
        repo = SqlOverrideRepository(session)
        cls = repo._model_cls(content_type)
        assert cls is not None

    def test_model_cls_unknown_type_raises(self):
        session = _make_session()
        repo = SqlOverrideRepository(session)
        with pytest.raises(ValueError, match="Unknown override"):
            repo._model_cls(MagicMock(value="nonexistent"))

    def test_list_overrides_for_organization(self):
        session = _make_session()
        chain = session.query.return_value
        m = RoleOverrideModel()
        m.id = 1
        m.organization_id = 5
        m.base_content_id = 1
        m.override_fields = {}
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        chain.all.return_value = [m]
        repo = SqlOverrideRepository(session)
        results = repo.list_overrides_for_organization(5, ContentType.ROLE)
        assert len(results) == 1
        assert isinstance(results[0], OverrideRecord)


# ═══════════════════════════════════════════════════════════════════════════
# Audit Log Repository
# ═══════════════════════════════════════════════════════════════════════════


class TestSqlAuditLogRepository:
    def test_log_adds_model(self):
        session = _make_session()
        repo = SqlAuditLogRepository(session)
        repo.log(
            organization_id=5,
            actor_user_id=1,
            action="create",
            entity_type="template",
            entity_id=10,
            old_value=None,
            new_value={"name": "New"},
        )
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, AuditLogModel)
        assert added.action == "create"
        assert added.entity_type == "template"

    def test_log_does_not_flush(self):
        """Audit logs ride the main transaction — no explicit flush."""
        session = _make_session()
        repo = SqlAuditLogRepository(session)
        repo.log(
            organization_id=5,
            actor_user_id=1,
            action="delete",
            entity_type="role",
            entity_id=1,
        )
        session.flush.assert_not_called()

    def test_log_with_optional_fields(self):
        session = _make_session()
        repo = SqlAuditLogRepository(session)
        repo.log(
            organization_id=None,
            actor_user_id=1,
            action="update",
            entity_type="rubric",
            entity_id=20,
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )
        added = session.add.call_args[0][0]
        assert added.ip_address == "127.0.0.1"
        assert added.user_agent == "test-agent"


# ═══════════════════════════════════════════════════════════════════════════
# Pagination helper
# ═══════════════════════════════════════════════════════════════════════════


class TestPagination:
    def test_page_1(self):
        from app.admin.persistence.repositories import _paginate
        q = MagicMock()
        q.offset.return_value = q
        q.limit.return_value = q
        _paginate(q, page=1, per_page=10)
        q.offset.assert_called_once_with(0)
        q.limit.assert_called_once_with(10)

    def test_page_3(self):
        from app.admin.persistence.repositories import _paginate
        q = MagicMock()
        q.offset.return_value = q
        q.limit.return_value = q
        _paginate(q, page=3, per_page=20)
        q.offset.assert_called_once_with(40)
        q.limit.assert_called_once_with(20)

    def test_page_0_treated_as_1(self):
        from app.admin.persistence.repositories import _paginate
        q = MagicMock()
        q.offset.return_value = q
        q.limit.return_value = q
        _paginate(q, page=0, per_page=10)
        q.offset.assert_called_once_with(0)

    def test_negative_page_treated_as_1(self):
        from app.admin.persistence.repositories import _paginate
        q = MagicMock()
        q.offset.return_value = q
        q.limit.return_value = q
        _paginate(q, page=-5, per_page=10)
        q.offset.assert_called_once_with(0)
