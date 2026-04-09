--
-- Migration DEV-54: Self-Introduction as First Interview Question
--
-- Purpose:
--   1) Seed a DB-maintained preset pool of self-introduction prompts.
--   2) Enable self_introduction section in interview templates.
--   3) Keep template_structure.total_questions aligned (+question_count).
--
-- Date: 2026-04-09
-- Module: app/candidate + app/interview
-- Ticket: DEV-54
--
-- Rollback: DEV-54_self-introduction-first-question_rollback.sql
--

-- ============================================================================
-- PART 1: Seed self-introduction preset question pool
-- ============================================================================

-- Ensure sequence is aligned with existing rows to avoid duplicate PK on id
SELECT setval(
    pg_get_serial_sequence('public.questions', 'id'),
    COALESCE((SELECT MAX(id) FROM public.questions), 1),
    true
);

WITH seed(question_text, estimated_time_minutes) AS (
    VALUES
        ('Before we begin, could you briefly introduce yourself and highlight your current role, core strengths, and what kind of problems you enjoy solving most?', 4),
        ('Please give me a concise self-introduction: your background, your most relevant technical experience, and one recent project you are proud of.', 4),
        ('Let us start with a quick introduction. Tell me about your journey so far and the skills that best represent you as an engineer.', 4),
        ('Could you introduce yourself in 60-90 seconds, focusing on your experience level, preferred tech stack, and impact you have created?', 4),
        ('To kick off, please introduce yourself and share what motivates you professionally and what role you are currently targeting.', 4),
        ('Start with a short self-introduction covering your education/work path, strongest technical areas, and collaboration style.', 4),
        ('Please introduce yourself and summarize the two or three experiences that prepared you best for this interview.', 4),
        ('I would love to know you better first. Give a brief self-introduction and mention one challenge you solved recently.', 4)
)
INSERT INTO public.questions (
    question_text,
    answer_text,
    question_type,
    difficulty,
    scope,
    organization_id,
    source_type,
    estimated_time_minutes,
    is_active
)
SELECT
    s.question_text,
    NULL,
    'behavioral'::public.question_type,
    'easy'::public.difficulty_level,
    'organization',
    1,
    'self_intro_preset',
    s.estimated_time_minutes,
    true
FROM seed s
WHERE NOT EXISTS (
    SELECT 1
    FROM public.questions q
    WHERE q.source_type = 'self_intro_preset'
      AND q.question_text = s.question_text
);

-- ============================================================================
-- PART 2: Enable self_introduction in template_structure and adjust totals
-- ============================================================================

WITH targets AS (
    SELECT
        it.id,
        it.template_structure,
        COALESCE((it.template_structure->>'total_questions')::int, 0) AS total_before,
        COALESCE((it.template_structure #>> '{sections,self_introduction,question_count}')::int, 1) AS add_count
    FROM public.interview_templates it
    WHERE jsonb_typeof(it.template_structure) = 'object'
      AND jsonb_typeof(it.template_structure->'sections') = 'object'
      AND jsonb_typeof(it.template_structure->'sections'->'self_introduction') = 'object'
      AND COALESCE((it.template_structure #>> '{sections,self_introduction,enabled}')::boolean, false) = false
),
patched AS (
    SELECT
        t.id,
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    t.template_structure,
                    '{sections,self_introduction,enabled}',
                    'true'::jsonb,
                    true
                ),
                '{sections,self_introduction,question_count}',
                to_jsonb(t.add_count),
                true
            ),
            '{total_questions}',
            to_jsonb(t.total_before + t.add_count),
            true
        ) AS patched_structure
    FROM targets t
)
UPDATE public.interview_templates it
SET
    template_structure = p.patched_structure,
    updated_at = now()
FROM patched p
WHERE it.id = p.id;
