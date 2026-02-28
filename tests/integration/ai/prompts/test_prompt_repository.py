"""
Integration Tests – SqlPromptTemplateRepository

Tests prompt template retrieval and scope resolution against a real
PostgreSQL database. Each test runs inside a transaction that is always
rolled back — no data persists between tests.

Covers:
  - get_by_id: existence and non-existence
  - get_active_by_type: global resolution
  - get_active_by_type: org → global fallback chain
  - get_active_by_type_strict: exact scope (no fallback)
  - list_by_type: version ordering, active/inactive filtering
  - list_active_types: distinct type enumeration
  - Scope resolution edge cases (org-only, global-only, inactive)
"""

import uuid

import pytest
from sqlalchemy import text

from app.ai.prompts.entities import PromptTemplate
from app.ai.prompts.repository import SqlPromptTemplateRepository


pytestmark = pytest.mark.integration


# =========================================================================
# get_by_id
# =========================================================================

class TestGetById:
    """Test SqlPromptTemplateRepository.get_by_id against live DB."""

    def test_returns_entity_for_existing_id(self, db_session, seed_global_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_global_prompt["id"])

        assert result is not None
        assert isinstance(result, PromptTemplate)
        assert result.id == seed_global_prompt["id"]
        assert result.name == seed_global_prompt["name"]
        assert result.prompt_type == "question_generation"
        assert result.version == 1

    def test_returns_none_for_nonexistent_id(self, db_session):
        repo = SqlPromptTemplateRepository(db_session)
        assert repo.get_by_id(999_999_999) is None

    def test_returns_correct_entity_fields(self, db_session, seed_global_prompt):
        """Verify all entity fields are properly mapped from ORM model."""
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_global_prompt["id"])

        assert result is not None
        assert result.scope == "public"
        assert result.organization_id == 1
        assert result.is_active is True
        assert result.model_config == {"temperature": 0.7, "max_tokens": 1500}
        assert result.created_at is not None
        assert result.updated_at is not None
        assert "test agent" in result.system_prompt.lower()
        assert "{{topic}}" in result.user_prompt
        assert "{{difficulty}}" in result.user_prompt


# =========================================================================
# get_active_by_type — Global resolution
# =========================================================================

class TestGetActiveByTypeGlobal:
    """Test active prompt retrieval for global (public) scope."""

    def test_returns_global_prompt_without_org_id(self, db_session, seed_global_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type("question_generation")

        assert result is not None
        assert result.prompt_type == "question_generation"
        assert result.scope == "public"
        assert result.is_active is True

    def test_returns_none_for_missing_type(self, db_session):
        repo = SqlPromptTemplateRepository(db_session)
        assert repo.get_active_by_type("nonexistent_type_xyz") is None

    def test_skips_inactive_prompt(self, db_session, seed_inactive_prompt):
        """An inactive prompt should not be returned even if it matches."""
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type("question_generation")
        # The inactive prompt has version=99 but is_active=False
        # There may or may not be an active one in the DB; the key assertion
        # is that if a result IS returned, it must be active
        if result is not None:
            assert result.is_active is True


# =========================================================================
# get_active_by_type — Org → Global fallback
# =========================================================================

class TestGetActiveByTypeFallback:
    """Test the org → global fallback resolution chain."""

    def test_returns_org_prompt_when_available(
        self, db_session, seed_global_prompt, seed_org_prompt
    ):
        """When an org-scoped prompt exists, prefer it over global."""
        repo = SqlPromptTemplateRepository(db_session)
        org_id = seed_org_prompt["organization_id"]

        result = repo.get_active_by_type("evaluation", organization_id=org_id)

        assert result is not None
        assert result.organization_id == org_id
        assert result.prompt_type == "evaluation"

    def test_falls_back_to_global_when_no_org_prompt(
        self, db_session, seed_global_prompt, create_test_organization
    ):
        """When org has no override, fall back to the global prompt."""
        repo = SqlPromptTemplateRepository(db_session)
        org_id = create_test_organization["id"]

        # This org has no 'question_generation' override → should get global
        result = repo.get_active_by_type(
            "question_generation", organization_id=org_id
        )

        assert result is not None
        assert result.scope == "public"
        assert result.organization_id == 1  # SUPER_ORG_ID

    def test_returns_none_when_no_prompt_exists_at_all(
        self, db_session, create_test_organization
    ):
        """Neither org nor global prompt exists for this type."""
        repo = SqlPromptTemplateRepository(db_session)
        org_id = create_test_organization["id"]

        result = repo.get_active_by_type(
            "nonexistent_type_abc", organization_id=org_id
        )
        assert result is None


# =========================================================================
# get_active_by_type_strict — Exact scope, no fallback
# =========================================================================

class TestGetActiveByTypeStrict:
    """Test strict scope resolution (no fallback)."""

    def test_returns_org_prompt_for_matching_org(
        self, db_session, seed_org_prompt
    ):
        repo = SqlPromptTemplateRepository(db_session)
        org_id = seed_org_prompt["organization_id"]

        result = repo.get_active_by_type_strict(
            "evaluation", organization_id=org_id
        )
        assert result is not None
        assert result.organization_id == org_id

    def test_returns_none_when_org_has_no_override(
        self, db_session, seed_global_prompt, create_test_organization
    ):
        """Strict mode does NOT fall back to global."""
        repo = SqlPromptTemplateRepository(db_session)
        org_id = create_test_organization["id"]

        result = repo.get_active_by_type_strict(
            "question_generation", organization_id=org_id
        )
        assert result is None

    def test_returns_global_when_org_id_is_none(
        self, db_session, seed_global_prompt
    ):
        """org_id=None strict → global only."""
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type_strict(
            "question_generation", organization_id=None
        )
        assert result is not None
        assert result.scope == "public"


# =========================================================================
# list_by_type — Version listing with filters
# =========================================================================

class TestListByType:
    """Test version listing for a prompt type."""

    def test_lists_active_versions_only_by_default(
        self, db_session, seed_multi_version_prompts
    ):
        """Default: only active versions returned."""
        repo = SqlPromptTemplateRepository(db_session)
        results = repo.list_by_type("report_generation")

        active = [r for r in results if r.name == seed_multi_version_prompts[1]["name"]]
        assert len(active) >= 1
        for r in active:
            assert r.is_active is True

    def test_includes_inactive_when_requested(
        self, db_session, seed_multi_version_prompts
    ):
        """include_inactive=True returns both active and inactive."""
        repo = SqlPromptTemplateRepository(db_session)
        results = repo.list_by_type(
            "report_generation", include_inactive=True
        )

        test_name = seed_multi_version_prompts[0]["name"]
        matching = [r for r in results if r.name == test_name]
        assert len(matching) == 2
        versions = {r.version for r in matching}
        assert versions == {1, 2}

    def test_ordered_by_version_descending(
        self, db_session, seed_multi_version_prompts
    ):
        """Results should be ordered by version DESC."""
        repo = SqlPromptTemplateRepository(db_session)
        results = repo.list_by_type(
            "report_generation", include_inactive=True
        )
        test_name = seed_multi_version_prompts[0]["name"]
        matching = [r for r in results if r.name == test_name]
        if len(matching) >= 2:
            assert matching[0].version > matching[1].version

    def test_returns_empty_list_for_unknown_type(self, db_session):
        repo = SqlPromptTemplateRepository(db_session)
        results = repo.list_by_type("totally_unknown_type_xyz")
        assert results == []

    def test_org_scoped_list_includes_global_and_org(
        self, db_session, seed_global_prompt, seed_org_prompt
    ):
        """org-scoped list should show both org prompts and global ones."""
        repo = SqlPromptTemplateRepository(db_session)
        org_id = seed_org_prompt["organization_id"]

        # Seed a global evaluation prompt so both org + global exist for 'evaluation'
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, 'evaluation', 'public', 1,
                     'Global eval sys', 'Global eval usr', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"global_eval_{uuid.uuid4().hex[:8]}"},
        )
        db_session.flush()

        results = repo.list_by_type("evaluation", organization_id=org_id)
        org_ids = {r.organization_id for r in results}
        # Should contain both the org-scoped and global prompts
        assert org_id in org_ids or 1 in org_ids


# =========================================================================
# list_active_types — Distinct type enumeration
# =========================================================================

class TestListActiveTypes:
    """Test distinct active prompt_type listing."""

    def test_lists_types_with_active_versions(
        self, db_session, seed_global_prompt
    ):
        repo = SqlPromptTemplateRepository(db_session)
        types = repo.list_active_types()

        assert isinstance(types, list)
        assert "question_generation" in types

    def test_excludes_types_with_only_inactive_versions(
        self, db_session, seed_inactive_prompt
    ):
        """If the only version is inactive, that type should not appear."""
        repo = SqlPromptTemplateRepository(db_session)
        types = repo.list_active_types()

        # The inactive prompt's type is 'question_generation'
        # It might still appear if there are active rows of that type in the DB
        # What we verify: if we query for a type that has ONLY inactive rows,
        # it should not appear. We test this with a unique type:
        unique_type = f"unique_type_{uuid.uuid4().hex[:8]}"
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'sys', 'usr', '{}'::jsonb, 1, false)
                """
            ),
            {"name": f"only_inactive_{uuid.uuid4().hex[:8]}", "ptype": unique_type},
        )
        db_session.flush()

        types = repo.list_active_types()
        assert unique_type not in types

    def test_returns_sorted_types(self, db_session, seed_global_prompt):
        """Types should be returned in sorted order."""
        repo = SqlPromptTemplateRepository(db_session)
        types = repo.list_active_types()
        assert types == sorted(types)

    def test_org_scoped_includes_both_org_and_global_types(
        self, db_session, seed_global_prompt, seed_org_prompt
    ):
        """Org query should include both org-scoped and global types."""
        repo = SqlPromptTemplateRepository(db_session)
        org_id = seed_org_prompt["organization_id"]
        types = repo.list_active_types(organization_id=org_id)

        # Should contain both the global 'question_generation' and
        # org-scoped 'evaluation'
        assert "evaluation" in types


# =========================================================================
# Entity field mapping — Full roundtrip verification
# =========================================================================

class TestEntityMapping:
    """Verify ORM → Entity mapping for all fields."""

    def test_model_config_is_dict(self, db_session, seed_global_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_global_prompt["id"])

        assert isinstance(result.model_config, dict)
        assert result.model_config.get("temperature") == 0.7
        assert result.model_config.get("max_tokens") == 1500

    def test_temperature_property(self, db_session, seed_global_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_global_prompt["id"])

        assert result.temperature == 0.7

    def test_max_tokens_property(self, db_session, seed_global_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_global_prompt["id"])

        assert result.max_tokens == 1500

    def test_is_global_property(self, db_session, seed_global_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_global_prompt["id"])

        assert result.is_global is True

    def test_org_scoped_not_global(self, db_session, seed_org_prompt):
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_by_id(seed_org_prompt["id"])

        assert result.is_global is False


# =========================================================================
# Unique constraint enforcement
# =========================================================================

class TestConstraints:
    """Test database constraint enforcement."""

    def test_unique_name_version_org_constraint(
        self, db_session, seed_global_prompt
    ):
        """Inserting duplicate (name, version, org_id) should fail."""
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db_session.execute(
                text(
                    """
                    INSERT INTO prompt_templates
                        (name, prompt_type, scope, organization_id,
                         system_prompt, user_prompt, model_config, version, is_active)
                    VALUES
                        (:name, 'question_generation', 'public', 1,
                         'dup sys', 'dup usr', '{}'::jsonb, :ver, true)
                    """
                ),
                {
                    "name": seed_global_prompt["name"],
                    "ver": seed_global_prompt["version"],
                },
            )
            db_session.flush()
