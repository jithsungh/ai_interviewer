--
-- Migration DEV-37: Generic Fallback Questions Table
--
-- Purpose: Create the generic_fallback_questions table used by the
--          question/generation module as a last-resort fallback
--          when LLM generation fails after max retries.
-- Date: 2026-03-01
-- Module: app/question/generation
-- Ticket: DEV-37
--
-- New tables:
--   1. generic_fallback_questions
--
-- Invariants preserved:
--   - No FK to questions table (fallback pool is independent)
--   - No template/submission coupling (stateless lookup)
--   - No SRS invariant broken (this is additive, no schema modification)
--   - No ERD invariant violated (new leaf table, no references TO it)
--   - No existing module breaks (no column changes to existing tables)
--   - No data corruption risk (new table, empty on creation)
--   - No performance regression (B-tree composite + partial indexes)
--
-- Rollback: See DEV-37_generic-fallback-questions_rollback.sql
--

-- ============================================================================
-- PART 1: generic_fallback_questions
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.generic_fallback_questions_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE IF NOT EXISTS public.generic_fallback_questions (
    id              bigint NOT NULL DEFAULT nextval('public.generic_fallback_questions_id_seq'::regclass),
    question_type   varchar(50) NOT NULL,
    difficulty      varchar(20) NOT NULL,
    topic           varchar(100) NOT NULL,
    question_text   text NOT NULL,
    expected_answer text NOT NULL,
    estimated_time_seconds integer NOT NULL DEFAULT 120,
    is_active       boolean NOT NULL DEFAULT true,
    usage_count     integer NOT NULL DEFAULT 0,
    metadata        jsonb,
    created_at      timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT generic_fallback_questions_pkey PRIMARY KEY (id),
    CONSTRAINT generic_fallback_difficulty_check CHECK (difficulty IN ('easy', 'medium', 'hard')),
    CONSTRAINT generic_fallback_question_type_check CHECK (
        question_type IN ('behavioral', 'technical', 'situational', 'coding')
    ),
    CONSTRAINT generic_fallback_estimated_time_check CHECK (estimated_time_seconds > 0)
);

ALTER SEQUENCE public.generic_fallback_questions_id_seq
    OWNED BY public.generic_fallback_questions.id;

-- Composite index for the primary lookup pattern (difficulty + topic + active)
CREATE INDEX IF NOT EXISTS idx_generic_fallback_diff_topic_active
    ON public.generic_fallback_questions (difficulty, topic, is_active)
    WHERE (is_active = true);

-- Index for broader difficulty-only lookup
CREATE INDEX IF NOT EXISTS idx_generic_fallback_difficulty_active
    ON public.generic_fallback_questions (difficulty, usage_count)
    WHERE (is_active = true);

COMMENT ON TABLE public.generic_fallback_questions
    IS 'Pre-seeded generic questions used as last-resort fallback when LLM generation fails.';

-- ============================================================================
-- PART 2: Seed data — minimal set of generic fallback questions
-- ============================================================================

INSERT INTO public.generic_fallback_questions
    (question_type, difficulty, topic, question_text, expected_answer, estimated_time_seconds)
VALUES
    -- Behavioral fallbacks
    ('behavioral', 'easy', 'communication',
     'Describe a time when you had to explain a complex idea to someone without a technical background. How did you approach it?',
     'Key points: audience awareness, simplification without losing meaning, use of analogies, checking understanding, feedback loop.',
     120),

    ('behavioral', 'medium', 'teamwork',
     'Tell me about a situation where you disagreed with a team member on an approach. How did you resolve the conflict and what was the outcome?',
     'Key points: active listening, empathy, compromise or data-driven resolution, outcome, lessons learned.',
     180),

    ('behavioral', 'hard', 'leadership',
     'Describe a scenario where you had to lead a failing project. What steps did you take to turn things around and what were the results?',
     'Key points: root-cause analysis, stakeholder communication, re-prioritisation, team morale, measurable outcome.',
     240),

    -- Technical fallbacks
    ('technical', 'easy', 'algorithms',
     'Explain the difference between a stack and a queue. When would you use each in a real application?',
     'Key points: LIFO vs FIFO, use-cases (undo/redo, BFS, call stack), time complexity of operations.',
     120),

    ('technical', 'medium', 'system_design',
     'How would you design a URL shortening service? Walk me through the key components and trade-offs.',
     'Key points: hashing/encoding, storage, redirection, analytics, scaling reads vs writes, collision handling.',
     240),

    ('technical', 'hard', 'distributed_systems',
     'Explain the CAP theorem and describe how it applies when designing a globally distributed database. Give concrete trade-off examples.',
     'Key points: Consistency, Availability, Partition tolerance, CP vs AP systems, real examples (DynamoDB, Spanner), eventual consistency.',
     300),

    -- Situational fallbacks
    ('situational', 'easy', 'problem_solving',
     'If you were assigned a task with unclear requirements, what steps would you take before starting implementation?',
     'Key points: ask clarifying questions, identify stakeholders, define scope, document assumptions, confirm before proceeding.',
     120),

    ('situational', 'medium', 'decision_making',
     'Imagine you need to choose between two technology stacks for a new project. What criteria would you evaluate, and how would you make the decision?',
     'Key points: team expertise, community support, performance, scalability, maintainability, cost, time-to-market.',
     180),

    ('situational', 'hard', 'crisis_management',
     'Your production system is experiencing intermittent failures during peak traffic. Walk me through your incident response approach from detection to resolution.',
     'Key points: alerting, triage, communication, rollback vs hotfix, root-cause analysis, post-mortem, prevention.',
     300)

ON CONFLICT DO NOTHING;
