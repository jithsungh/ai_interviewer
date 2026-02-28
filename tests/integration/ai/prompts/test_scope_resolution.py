"""
Integration Tests – Prompt Scope Resolution

Focused tests on the multi-tenancy scope fallback chain:
  org-scoped active → global active → None

These tests exercise the core business rule that organizations can
override global prompts while falling back to them when no override exists.
"""

import uuid

import pytest
from sqlalchemy import text

from app.ai.prompts.repository import SqlPromptTemplateRepository
from app.ai.prompts.protocols import SUPER_ORG_ID


pytestmark = pytest.mark.integration


class TestScopeResolutionChain:
    """
    Validate the full scope fallback chain:
      1. Org-scoped active prompt (preferred)
      2. Global active prompt (fallback)
      3. None
    """

    def test_org_override_takes_priority(self, db_session, create_test_organization):
        """When org has its own prompt, it wins over global."""
        org_id = create_test_organization["id"]
        ptype = f"scope_test_{uuid.uuid4().hex[:8]}"

        # Insert global prompt
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'Global system', 'Global user', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"global_{ptype}", "ptype": ptype},
        )

        # Insert org-scoped prompt (same type)
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'organization', :org_id,
                     'Org system', 'Org user', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"org_{ptype}", "ptype": ptype, "org_id": org_id},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type(ptype, organization_id=org_id)

        assert result is not None
        assert result.organization_id == org_id
        assert result.system_prompt == "Org system"

    def test_global_fallback_when_org_has_no_override(
        self, db_session, create_test_organization
    ):
        """When org has no override, global prompt is returned."""
        org_id = create_test_organization["id"]
        ptype = f"fallback_test_{uuid.uuid4().hex[:8]}"

        # Insert ONLY a global prompt
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'Global only system', 'Global only user', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"global_{ptype}", "ptype": ptype},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type(ptype, organization_id=org_id)

        assert result is not None
        assert result.organization_id == SUPER_ORG_ID
        assert result.scope == "public"
        assert result.system_prompt == "Global only system"

    def test_none_when_no_prompt_at_any_scope(
        self, db_session, create_test_organization
    ):
        """When neither org nor global prompt exists, return None."""
        org_id = create_test_organization["id"]
        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type(
            f"nonexistent_{uuid.uuid4().hex[:8]}",
            organization_id=org_id,
        )
        assert result is None

    def test_inactive_org_prompt_does_not_block_global_fallback(
        self, db_session, create_test_organization
    ):
        """
        An INACTIVE org-scoped prompt should NOT prevent fallback to global.

        Scenario:
        - org has inactive 'evaluation' prompt
        - global has active 'evaluation' prompt
        - Expected: global prompt returned (fallback)
        """
        org_id = create_test_organization["id"]
        ptype = f"inactive_fallback_{uuid.uuid4().hex[:8]}"

        # Inactive org prompt
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'organization', :org_id,
                     'Inactive org sys', 'Inactive org usr', '{}'::jsonb, 1, false)
                """
            ),
            {
                "name": f"inactive_org_{ptype}",
                "ptype": ptype,
                "org_id": org_id,
            },
        )

        # Active global prompt
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'Active global sys', 'Active global usr', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"active_global_{ptype}", "ptype": ptype},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type(ptype, organization_id=org_id)

        assert result is not None
        assert result.scope == "public"
        assert result.organization_id == SUPER_ORG_ID
        assert result.system_prompt == "Active global sys"


class TestSuperOrgIdBypass:
    """Verify SUPER_ORG_ID (1) is treated as global, not as an org scope."""

    def test_super_org_id_resolves_as_global(self, db_session):
        """Passing SUPER_ORG_ID as organization_id should resolve global only."""
        ptype = f"super_org_{uuid.uuid4().hex[:8]}"

        # Insert global prompt
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'Super org global', 'Super org global usr', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"super_{ptype}", "ptype": ptype},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type(ptype, organization_id=SUPER_ORG_ID)

        assert result is not None
        assert result.organization_id == SUPER_ORG_ID
        assert result.scope == "public"

    def test_none_org_id_resolves_global(self, db_session):
        """organization_id=None should resolve global prompts only."""
        ptype = f"none_org_{uuid.uuid4().hex[:8]}"

        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'None org global', 'None org global usr', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"noneorg_{ptype}", "ptype": ptype},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)
        result = repo.get_active_by_type(ptype, organization_id=None)

        assert result is not None
        assert result.scope == "public"


class TestStrictVsFallback:
    """Compare strict vs fallback resolution for same data."""

    def test_strict_refuses_fallback(self, db_session, create_test_organization):
        """
        Strict mode returns None where fallback mode returns global.
        """
        org_id = create_test_organization["id"]
        ptype = f"strict_test_{uuid.uuid4().hex[:8]}"

        # Only global exists
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     'Global sys', 'Global usr', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"strict_g_{ptype}", "ptype": ptype},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)

        # Fallback → returns global
        fallback_result = repo.get_active_by_type(ptype, organization_id=org_id)
        assert fallback_result is not None
        assert fallback_result.scope == "public"

        # Strict → returns None (org has no override)
        strict_result = repo.get_active_by_type_strict(
            ptype, organization_id=org_id
        )
        assert strict_result is None

    def test_both_return_org_when_org_exists(
        self, db_session, create_test_organization
    ):
        """When org-scoped prompt exists, both modes return it."""
        org_id = create_test_organization["id"]
        ptype = f"both_test_{uuid.uuid4().hex[:8]}"

        # Org-scoped prompt
        db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'organization', :org_id,
                     'Org sys', 'Org usr', '{}'::jsonb, 1, true)
                """
            ),
            {"name": f"both_org_{ptype}", "ptype": ptype, "org_id": org_id},
        )
        db_session.flush()

        repo = SqlPromptTemplateRepository(db_session)

        fallback = repo.get_active_by_type(ptype, organization_id=org_id)
        strict = repo.get_active_by_type_strict(ptype, organization_id=org_id)

        assert fallback is not None
        assert strict is not None
        assert fallback.organization_id == org_id
        assert strict.organization_id == org_id
