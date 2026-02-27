--
-- Migration DEV-25: Admin Override Tables
--
-- Purpose: Create override tables for multi-tenant content customization.
--          Tenants override super-org (org_id=1) base content without mutating it.
-- Date: 2026-02-27
-- Module: app/admin/persistence
-- Ticket: DEV-25
--
-- New tables:
--   1. template_overrides
--   2. rubric_overrides
--   3. role_overrides
--   4. topic_overrides
--   5. question_overrides
--   6. coding_problem_overrides
--
-- Rollback: See DEV-25_admin_override_tables_rollback.sql
--

-- ============================================================================
-- PART 1: template_overrides
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.template_overrides_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE public.template_overrides (
    id              bigint NOT NULL DEFAULT nextval('public.template_overrides_id_seq'::regclass),
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb  NOT NULL DEFAULT '{}'::jsonb,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),
    updated_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT template_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT template_overrides_org_base_uq UNIQUE (organization_id, base_content_id),
    CONSTRAINT template_overrides_organization_id_fkey
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE,
    CONSTRAINT template_overrides_base_content_id_fkey
        FOREIGN KEY (base_content_id) REFERENCES public.interview_templates(id) ON DELETE CASCADE
);

CREATE INDEX idx_template_overrides_org ON public.template_overrides (organization_id);
CREATE INDEX idx_template_overrides_base ON public.template_overrides (base_content_id);
CREATE INDEX idx_template_overrides_active ON public.template_overrides (is_active) WHERE (is_active = true);

COMMENT ON TABLE public.template_overrides IS 'Tenant-specific overrides for super-org interview templates.';


-- ============================================================================
-- PART 2: rubric_overrides
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.rubric_overrides_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE public.rubric_overrides (
    id              bigint NOT NULL DEFAULT nextval('public.rubric_overrides_id_seq'::regclass),
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb  NOT NULL DEFAULT '{}'::jsonb,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),
    updated_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT rubric_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT rubric_overrides_org_base_uq UNIQUE (organization_id, base_content_id),
    CONSTRAINT rubric_overrides_organization_id_fkey
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE,
    CONSTRAINT rubric_overrides_base_content_id_fkey
        FOREIGN KEY (base_content_id) REFERENCES public.rubrics(id) ON DELETE CASCADE
);

CREATE INDEX idx_rubric_overrides_org ON public.rubric_overrides (organization_id);
CREATE INDEX idx_rubric_overrides_base ON public.rubric_overrides (base_content_id);
CREATE INDEX idx_rubric_overrides_active ON public.rubric_overrides (is_active) WHERE (is_active = true);

COMMENT ON TABLE public.rubric_overrides IS 'Tenant-specific overrides for super-org rubrics.';


-- ============================================================================
-- PART 3: role_overrides
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.role_overrides_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE public.role_overrides (
    id              bigint NOT NULL DEFAULT nextval('public.role_overrides_id_seq'::regclass),
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb  NOT NULL DEFAULT '{}'::jsonb,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),
    updated_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT role_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT role_overrides_org_base_uq UNIQUE (organization_id, base_content_id),
    CONSTRAINT role_overrides_organization_id_fkey
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE,
    CONSTRAINT role_overrides_base_content_id_fkey
        FOREIGN KEY (base_content_id) REFERENCES public.roles(id) ON DELETE CASCADE
);

CREATE INDEX idx_role_overrides_org ON public.role_overrides (organization_id);
CREATE INDEX idx_role_overrides_base ON public.role_overrides (base_content_id);
CREATE INDEX idx_role_overrides_active ON public.role_overrides (is_active) WHERE (is_active = true);

COMMENT ON TABLE public.role_overrides IS 'Tenant-specific overrides for super-org roles.';


-- ============================================================================
-- PART 4: topic_overrides
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.topic_overrides_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE public.topic_overrides (
    id              bigint NOT NULL DEFAULT nextval('public.topic_overrides_id_seq'::regclass),
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb  NOT NULL DEFAULT '{}'::jsonb,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),
    updated_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT topic_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT topic_overrides_org_base_uq UNIQUE (organization_id, base_content_id),
    CONSTRAINT topic_overrides_organization_id_fkey
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE,
    CONSTRAINT topic_overrides_base_content_id_fkey
        FOREIGN KEY (base_content_id) REFERENCES public.topics(id) ON DELETE CASCADE
);

CREATE INDEX idx_topic_overrides_org ON public.topic_overrides (organization_id);
CREATE INDEX idx_topic_overrides_base ON public.topic_overrides (base_content_id);
CREATE INDEX idx_topic_overrides_active ON public.topic_overrides (is_active) WHERE (is_active = true);

COMMENT ON TABLE public.topic_overrides IS 'Tenant-specific overrides for super-org topics.';


-- ============================================================================
-- PART 5: question_overrides
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.question_overrides_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE public.question_overrides (
    id              bigint NOT NULL DEFAULT nextval('public.question_overrides_id_seq'::regclass),
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb  NOT NULL DEFAULT '{}'::jsonb,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),
    updated_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT question_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT question_overrides_org_base_uq UNIQUE (organization_id, base_content_id),
    CONSTRAINT question_overrides_organization_id_fkey
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE,
    CONSTRAINT question_overrides_base_content_id_fkey
        FOREIGN KEY (base_content_id) REFERENCES public.questions(id) ON DELETE CASCADE
);

CREATE INDEX idx_question_overrides_org ON public.question_overrides (organization_id);
CREATE INDEX idx_question_overrides_base ON public.question_overrides (base_content_id);
CREATE INDEX idx_question_overrides_active ON public.question_overrides (is_active) WHERE (is_active = true);

COMMENT ON TABLE public.question_overrides IS 'Tenant-specific overrides for super-org questions.';


-- ============================================================================
-- PART 6: coding_problem_overrides
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.coding_problem_overrides_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE public.coding_problem_overrides (
    id              bigint NOT NULL DEFAULT nextval('public.coding_problem_overrides_id_seq'::regclass),
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb  NOT NULL DEFAULT '{}'::jsonb,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),
    updated_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT coding_problem_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT coding_problem_overrides_org_base_uq UNIQUE (organization_id, base_content_id),
    CONSTRAINT coding_problem_overrides_organization_id_fkey
        FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE,
    CONSTRAINT coding_problem_overrides_base_content_id_fkey
        FOREIGN KEY (base_content_id) REFERENCES public.coding_problems(id) ON DELETE CASCADE
);

CREATE INDEX idx_coding_problem_overrides_org ON public.coding_problem_overrides (organization_id);
CREATE INDEX idx_coding_problem_overrides_base ON public.coding_problem_overrides (base_content_id);
CREATE INDEX idx_coding_problem_overrides_active ON public.coding_problem_overrides (is_active) WHERE (is_active = true);

COMMENT ON TABLE public.coding_problem_overrides IS 'Tenant-specific overrides for super-org coding problems.';
