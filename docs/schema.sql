--
-- PostgreSQL database dump
--

\restrict 8q91naVy8neIQ4clJuUYcglOmRD3MVVGTwJSCZfKRIXTayzG9cSFNq80OzhKct2

-- Dumped from database version 17.8 (Debian 17.8-1.pgdg13+1)
-- Dumped by pg_dump version 17.9 (Ubuntu 17.9-1.pgdg24.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: admin_role; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.admin_role AS ENUM (
    'superadmin',
    'admin',
    'read_only'
);


ALTER TYPE public.admin_role OWNER TO jithsungh;

--
-- Name: admin_status; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.admin_status AS ENUM (
    'active',
    'inactive',
    'suspended'
);


ALTER TYPE public.admin_status OWNER TO jithsungh;

--
-- Name: candidate_plan; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.candidate_plan AS ENUM (
    'free',
    'pro',
    'prime'
);


ALTER TYPE public.candidate_plan OWNER TO jithsungh;

--
-- Name: code_execution_status; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.code_execution_status AS ENUM (
    'pending',
    'running',
    'passed',
    'failed',
    'error',
    'timeout',
    'memory_exceeded'
);


ALTER TYPE public.code_execution_status OWNER TO jithsungh;

--
-- Name: coding_topic_type; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.coding_topic_type AS ENUM (
    'data_structure',
    'algorithm',
    'pattern',
    'system_design',
    'language_specific',
    'traversal'
);


ALTER TYPE public.coding_topic_type OWNER TO jithsungh;

--
-- Name: difficulty_level; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.difficulty_level AS ENUM (
    'easy',
    'medium',
    'hard'
);


ALTER TYPE public.difficulty_level OWNER TO jithsungh;

--
-- Name: evaluator_type; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.evaluator_type AS ENUM (
    'ai',
    'human',
    'hybrid'
);


ALTER TYPE public.evaluator_type OWNER TO jithsungh;

--
-- Name: interview_mode; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.interview_mode AS ENUM (
    'async',
    'live',
    'hybrid'
);


ALTER TYPE public.interview_mode OWNER TO jithsungh;

--
-- Name: interview_scope; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.interview_scope AS ENUM (
    'global',
    'local',
    'only_invited'
);


ALTER TYPE public.interview_scope OWNER TO jithsungh;

--
-- Name: media_type; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.media_type AS ENUM (
    'video',
    'audio',
    'screen_recording'
);


ALTER TYPE public.media_type OWNER TO jithsungh;

--
-- Name: organization_plan; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.organization_plan AS ENUM (
    'free',
    'pro',
    'enterprise'
);


ALTER TYPE public.organization_plan OWNER TO jithsungh;

--
-- Name: organization_status; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.organization_status AS ENUM (
    'active',
    'inactive',
    'suspended'
);


ALTER TYPE public.organization_status OWNER TO jithsungh;

--
-- Name: organization_type; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.organization_type AS ENUM (
    'company',
    'non_profit',
    'educational'
);


ALTER TYPE public.organization_type OWNER TO jithsungh;

--
-- Name: problem_pipeline_status; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.problem_pipeline_status AS ENUM (
    'pending',
    'solution_fetched',
    'tests_validated',
    'templates_validated',
    'imported'
);


ALTER TYPE public.problem_pipeline_status OWNER TO jithsungh;

--
-- Name: problem_source; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.problem_source AS ENUM (
    'leetcode'
);


ALTER TYPE public.problem_source OWNER TO jithsungh;

--
-- Name: proctoring_severity; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.proctoring_severity AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);


ALTER TYPE public.proctoring_severity OWNER TO jithsungh;

--
-- Name: question_type; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.question_type AS ENUM (
    'behavioral',
    'technical',
    'situational',
    'coding'
);


ALTER TYPE public.question_type OWNER TO jithsungh;

--
-- Name: report_type; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.report_type AS ENUM (
    'candidate_summary',
    'technical_breakdown',
    'behavioral_analysis',
    'proctoring_risk'
);


ALTER TYPE public.report_type OWNER TO jithsungh;

--
-- Name: submission_status; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.submission_status AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'expired',
    'cancelled',
    'reviewed'
);


ALTER TYPE public.submission_status OWNER TO jithsungh;

--
-- Name: template_scope; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.template_scope AS ENUM (
    'public',
    'organization',
    'private'
);


ALTER TYPE public.template_scope OWNER TO jithsungh;

--
-- Name: user_status; Type: TYPE; Schema: public; Owner: jithsungh
--

CREATE TYPE public.user_status AS ENUM (
    'active',
    'inactive',
    'banned'
);


ALTER TYPE public.user_status OWNER TO jithsungh;

--
-- Name: fn_audit_interview_submission_status_transition(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.fn_audit_interview_submission_status_transition() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    actor_value TEXT;
BEGIN
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;

    actor_value := NULLIF(current_setting('app.actor', true), '');

    INSERT INTO public.interview_submission_status_audit (
        submission_id,
        from_status,
        to_status,
        actor,
        occurred_at
    )
    VALUES (
        NEW.id,
        OLD.status::public.submission_status,
        NEW.status::public.submission_status,
        actor_value,
        now()
    );

    RETURN NEW;
END;
$$;


ALTER FUNCTION public.fn_audit_interview_submission_status_transition() OWNER TO postgres;

--
-- Name: fn_validate_interview_submission_status_transition(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.fn_validate_interview_submission_status_transition() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- only validate actual status changes
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.interview_submission_allowed_transitions t
        WHERE t.from_status = OLD.status::public.submission_status
          AND t.to_status = NEW.status::public.submission_status
    ) THEN
        RAISE EXCEPTION
            'Invalid interview_submissions.status transition: % -> % (submission_id=%)',
            OLD.status,
            NEW.status,
            OLD.id
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;


ALTER FUNCTION public.fn_validate_interview_submission_status_transition() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admins; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.admins (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    organization_id bigint NOT NULL,
    role public.admin_role NOT NULL,
    status public.admin_status DEFAULT 'active'::public.admin_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.admins OWNER TO jithsungh;

--
-- Name: admins_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.admins_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admins_id_seq OWNER TO jithsungh;

--
-- Name: admins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.admins_id_seq OWNED BY public.admins.id;


--
-- Name: audio_analytics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.audio_analytics (
    id bigint NOT NULL,
    interview_exchange_id bigint NOT NULL,
    transcript text,
    confidence_score numeric,
    speech_rate_wpm integer,
    filler_word_count integer,
    sentiment_score numeric,
    analysis_metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    transcript_finalized boolean DEFAULT false NOT NULL,
    language_detected character varying(10),
    speech_state character varying(20) DEFAULT 'complete'::character varying NOT NULL,
    pause_duration_ms integer,
    long_pause_count integer DEFAULT 0 NOT NULL,
    filler_rate numeric DEFAULT 0.0 NOT NULL,
    hesitation_detected boolean DEFAULT false NOT NULL,
    frustration_detected boolean DEFAULT false NOT NULL,
    audio_quality_score numeric,
    background_noise_detected boolean DEFAULT false NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    finalized_at timestamp with time zone,
    CONSTRAINT audio_analytics_confidence_range CHECK (((confidence_score IS NULL) OR ((confidence_score >= 0.0) AND (confidence_score <= 1.0)))),
    CONSTRAINT audio_analytics_sentiment_range CHECK (((sentiment_score IS NULL) OR ((sentiment_score >= '-1.0'::numeric) AND (sentiment_score <= 1.0)))),
    CONSTRAINT audio_analytics_speech_state_check CHECK (((speech_state)::text = ANY (ARRAY[('complete'::character varying)::text, ('incomplete'::character varying)::text, ('continuing'::character varying)::text])))
);


ALTER TABLE public.audio_analytics OWNER TO jithsungh;

--
-- Name: audio_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.audio_analytics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audio_analytics_id_seq OWNER TO jithsungh;

--
-- Name: audio_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.audio_analytics_id_seq OWNED BY public.audio_analytics.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.audit_logs (
    id bigint NOT NULL,
    organization_id bigint,
    actor_user_id bigint,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id bigint,
    old_value jsonb,
    new_value jsonb,
    ip_address inet,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO jithsungh;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.audit_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_logs_id_seq OWNER TO jithsungh;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: auth_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.auth_audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.auth_audit_log_id_seq OWNER TO jithsungh;

--
-- Name: auth_audit_log; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.auth_audit_log (
    id bigint DEFAULT nextval('public.auth_audit_log_id_seq'::regclass) NOT NULL,
    user_id bigint,
    event_type character varying(50) NOT NULL,
    ip_address inet,
    user_agent text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.auth_audit_log OWNER TO jithsungh;

--
-- Name: TABLE auth_audit_log; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.auth_audit_log IS 'Immutable audit log for all authentication events. INSERT-ONLY table.';


--
-- Name: COLUMN auth_audit_log.event_type; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.auth_audit_log.event_type IS 'Event type: login_success, login_failure, logout, token_refresh, password_change, admin_role_changed, user_status_changed, suspicious_activity';


--
-- Name: COLUMN auth_audit_log.metadata; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.auth_audit_log.metadata IS 'Additional context as JSON: {error_code, email, organization_id, admin_role, etc.}';


--
-- Name: candidate_career_insight_runs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candidate_career_insight_runs (
    id bigint NOT NULL,
    candidate_id bigint NOT NULL,
    industry text NOT NULL,
    seniority character varying(30) NOT NULL,
    insights jsonb DEFAULT '[]'::jsonb NOT NULL,
    generation_source character varying(20) DEFAULT 'fallback'::character varying NOT NULL,
    model_provider character varying(50),
    model_name character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.candidate_career_insight_runs OWNER TO postgres;

--
-- Name: candidate_career_insight_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candidate_career_insight_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candidate_career_insight_runs_id_seq OWNER TO postgres;

--
-- Name: candidate_career_insight_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.candidate_career_insight_runs_id_seq OWNED BY public.candidate_career_insight_runs.id;


--
-- Name: candidate_career_roadmaps; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candidate_career_roadmaps (
    id bigint NOT NULL,
    candidate_id bigint NOT NULL,
    insight_run_id bigint,
    industry text NOT NULL,
    target_role text NOT NULL,
    selected_insight jsonb,
    steps jsonb DEFAULT '[]'::jsonb NOT NULL,
    completed_levels jsonb DEFAULT '[]'::jsonb NOT NULL,
    current_level integer DEFAULT 1 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    generation_source character varying(20) DEFAULT 'fallback'::character varying NOT NULL,
    model_provider character varying(50),
    model_name character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT candidate_career_roadmaps_current_level_check CHECK (((current_level >= 1) AND (current_level <= 4)))
);


ALTER TABLE public.candidate_career_roadmaps OWNER TO postgres;

--
-- Name: candidate_career_roadmaps_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candidate_career_roadmaps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candidate_career_roadmaps_id_seq OWNER TO postgres;

--
-- Name: candidate_career_roadmaps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.candidate_career_roadmaps_id_seq OWNED BY public.candidate_career_roadmaps.id;


--
-- Name: candidate_practice_deck_runs; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.candidate_practice_deck_runs (
    id bigint NOT NULL,
    candidate_id bigint NOT NULL,
    role text NOT NULL,
    industry text NOT NULL,
    question_type character varying(30),
    difficulty character varying(20),
    source_question_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    flashcards jsonb DEFAULT '[]'::jsonb NOT NULL,
    bookmarked_indices jsonb DEFAULT '[]'::jsonb NOT NULL,
    mastered_indices jsonb DEFAULT '[]'::jsonb NOT NULL,
    current_card_index integer DEFAULT 0 NOT NULL,
    progress_percent integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    generation_source character varying(20) DEFAULT 'db'::character varying NOT NULL,
    model_provider character varying(50),
    model_name character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT candidate_practice_deck_runs_current_card_index_check CHECK ((current_card_index >= 0)),
    CONSTRAINT candidate_practice_deck_runs_progress_check CHECK (((progress_percent >= 0) AND (progress_percent <= 100)))
);


ALTER TABLE public.candidate_practice_deck_runs OWNER TO jithsungh;

--
-- Name: candidate_practice_deck_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.candidate_practice_deck_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candidate_practice_deck_runs_id_seq OWNER TO jithsungh;

--
-- Name: candidate_practice_deck_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.candidate_practice_deck_runs_id_seq OWNED BY public.candidate_practice_deck_runs.id;


--
-- Name: candidates; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.candidates (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    plan public.candidate_plan DEFAULT 'free'::public.candidate_plan NOT NULL,
    status public.user_status DEFAULT 'active'::public.user_status NOT NULL,
    profile_metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.candidates OWNER TO jithsungh;

--
-- Name: candidates_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.candidates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candidates_id_seq OWNER TO jithsungh;

--
-- Name: candidates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.candidates_id_seq OWNED BY public.candidates.id;


--
-- Name: code_execution_results; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.code_execution_results (
    id bigint NOT NULL,
    code_submission_id bigint NOT NULL,
    test_case_id bigint NOT NULL,
    passed boolean NOT NULL,
    actual_output text,
    runtime_ms integer,
    memory_kb integer,
    compiler_output text,
    runtime_output text,
    feedback text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    exit_code integer
);


ALTER TABLE public.code_execution_results OWNER TO jithsungh;

--
-- Name: code_execution_results_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.code_execution_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.code_execution_results_id_seq OWNER TO jithsungh;

--
-- Name: code_execution_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.code_execution_results_id_seq OWNED BY public.code_execution_results.id;


--
-- Name: code_submissions; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.code_submissions (
    id bigint NOT NULL,
    interview_exchange_id bigint NOT NULL,
    coding_problem_id bigint NOT NULL,
    language text NOT NULL,
    source_code text NOT NULL,
    execution_status public.code_execution_status DEFAULT 'pending'::public.code_execution_status NOT NULL,
    score numeric,
    execution_time_ms integer,
    memory_kb integer,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    executed_at timestamp with time zone
);


ALTER TABLE public.code_submissions OWNER TO jithsungh;

--
-- Name: code_submissions_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.code_submissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.code_submissions_id_seq OWNER TO jithsungh;

--
-- Name: code_submissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.code_submissions_id_seq OWNED BY public.code_submissions.id;


--
-- Name: coding_problem_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.coding_problem_overrides_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.coding_problem_overrides_id_seq OWNER TO jithsungh;

--
-- Name: coding_problem_overrides; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.coding_problem_overrides (
    id bigint DEFAULT nextval('public.coding_problem_overrides_id_seq'::regclass) NOT NULL,
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.coding_problem_overrides OWNER TO jithsungh;

--
-- Name: TABLE coding_problem_overrides; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.coding_problem_overrides IS 'Tenant-specific overrides for super-org coding problems.';


--
-- Name: coding_problem_topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.coding_problem_topics (
    coding_problem_id bigint NOT NULL,
    coding_topic_id bigint NOT NULL
);


ALTER TABLE public.coding_problem_topics OWNER TO jithsungh;

--
-- Name: coding_problems; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.coding_problems (
    id bigint NOT NULL,
    body text NOT NULL,
    difficulty public.difficulty_level NOT NULL,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    constraints text,
    estimated_time_minutes integer DEFAULT 30 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    source_name public.problem_source NOT NULL,
    source_id text NOT NULL,
    source_slug text,
    title text DEFAULT ''::text NOT NULL,
    description text,
    raw_content jsonb,
    content_overridden boolean DEFAULT false NOT NULL,
    overridden_content text,
    examples jsonb DEFAULT '[]'::jsonb,
    constraints_structured jsonb DEFAULT '[]'::jsonb,
    hints jsonb DEFAULT '[]'::jsonb,
    stats jsonb,
    code_snippets jsonb DEFAULT '{}'::jsonb,
    likes integer,
    dislikes integer,
    acceptance_rate numeric(5,2),
    pipeline_status public.problem_pipeline_status DEFAULT 'pending'::public.problem_pipeline_status NOT NULL
);


ALTER TABLE public.coding_problems OWNER TO jithsungh;

--
-- Name: coding_problems_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.coding_problems_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.coding_problems_id_seq OWNER TO jithsungh;

--
-- Name: coding_problems_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.coding_problems_id_seq OWNED BY public.coding_problems.id;


--
-- Name: coding_test_cases; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.coding_test_cases (
    id bigint NOT NULL,
    coding_problem_id bigint NOT NULL,
    input_data text NOT NULL,
    expected_output text NOT NULL,
    is_hidden boolean DEFAULT true NOT NULL,
    weight numeric DEFAULT 1.0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.coding_test_cases OWNER TO jithsungh;

--
-- Name: coding_test_cases_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.coding_test_cases_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.coding_test_cases_id_seq OWNER TO jithsungh;

--
-- Name: coding_test_cases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.coding_test_cases_id_seq OWNED BY public.coding_test_cases.id;


--
-- Name: coding_topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.coding_topics (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    topic_type public.coding_topic_type NOT NULL,
    parent_topic_id bigint,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    display_order integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.coding_topics OWNER TO jithsungh;

--
-- Name: coding_topics_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.coding_topics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.coding_topics_id_seq OWNER TO jithsungh;

--
-- Name: coding_topics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.coding_topics_id_seq OWNED BY public.coding_topics.id;


--
-- Name: difficulty_adaptation_log; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.difficulty_adaptation_log (
    id bigint NOT NULL,
    submission_id bigint NOT NULL,
    exchange_sequence_order integer NOT NULL,
    previous_difficulty character varying(20),
    previous_score numeric(5,2),
    previous_question_id bigint,
    adaptation_rule character varying(50) NOT NULL,
    threshold_up numeric(5,2),
    threshold_down numeric(5,2),
    max_difficulty_jump integer DEFAULT 1 NOT NULL,
    next_difficulty character varying(20) NOT NULL,
    adaptation_reason text NOT NULL,
    difficulty_changed boolean DEFAULT false NOT NULL,
    decided_at timestamp with time zone NOT NULL,
    rule_version character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.difficulty_adaptation_log OWNER TO jithsungh;

--
-- Name: TABLE difficulty_adaptation_log; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.difficulty_adaptation_log IS 'Immutable audit log for difficulty adaptation decisions (FR-4.4). INSERT-ONLY.';


--
-- Name: difficulty_adaptation_log_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.difficulty_adaptation_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.difficulty_adaptation_log_id_seq OWNER TO jithsungh;

--
-- Name: difficulty_adaptation_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.difficulty_adaptation_log_id_seq OWNED BY public.difficulty_adaptation_log.id;


--
-- Name: embeddings; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.embeddings (
    id bigint NOT NULL,
    organization_id bigint,
    source_type text NOT NULL,
    source_id bigint NOT NULL,
    model_id bigint NOT NULL,
    vector_ref text NOT NULL,
    dimensions integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.embeddings OWNER TO jithsungh;

--
-- Name: embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.embeddings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.embeddings_id_seq OWNER TO jithsungh;

--
-- Name: embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.embeddings_id_seq OWNED BY public.embeddings.id;


--
-- Name: evaluation_dimension_scores; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.evaluation_dimension_scores (
    id bigint NOT NULL,
    evaluation_id bigint NOT NULL,
    rubric_dimension_id bigint NOT NULL,
    score numeric NOT NULL,
    justification text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    max_score numeric
);


ALTER TABLE public.evaluation_dimension_scores OWNER TO jithsungh;

--
-- Name: evaluation_dimension_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.evaluation_dimension_scores_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.evaluation_dimension_scores_id_seq OWNER TO jithsungh;

--
-- Name: evaluation_dimension_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.evaluation_dimension_scores_id_seq OWNED BY public.evaluation_dimension_scores.id;


--
-- Name: evaluations; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.evaluations (
    id bigint NOT NULL,
    interview_exchange_id bigint NOT NULL,
    rubric_id bigint,
    model_id bigint,
    evaluator_type public.evaluator_type NOT NULL,
    total_score numeric,
    explanation jsonb,
    is_final boolean DEFAULT false NOT NULL,
    evaluated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    evaluated_by bigint,
    scoring_version text
);


ALTER TABLE public.evaluations OWNER TO jithsungh;

--
-- Name: evaluations_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.evaluations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.evaluations_id_seq OWNER TO jithsungh;

--
-- Name: evaluations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.evaluations_id_seq OWNED BY public.evaluations.id;


--
-- Name: generic_fallback_questions; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.generic_fallback_questions (
    id bigint NOT NULL,
    question_type character varying(50) NOT NULL,
    difficulty character varying(20) NOT NULL,
    topic character varying(100) NOT NULL,
    question_text text NOT NULL,
    expected_answer text NOT NULL,
    estimated_time_seconds integer DEFAULT 120 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    usage_count integer DEFAULT 0 NOT NULL,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT generic_fallback_difficulty_check CHECK (((difficulty)::text = ANY (ARRAY[('easy'::character varying)::text, ('medium'::character varying)::text, ('hard'::character varying)::text]))),
    CONSTRAINT generic_fallback_estimated_time_check CHECK ((estimated_time_seconds > 0)),
    CONSTRAINT generic_fallback_question_type_check CHECK (((question_type)::text = ANY (ARRAY[('behavioral'::character varying)::text, ('technical'::character varying)::text, ('situational'::character varying)::text, ('coding'::character varying)::text])))
);


ALTER TABLE public.generic_fallback_questions OWNER TO jithsungh;

--
-- Name: TABLE generic_fallback_questions; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.generic_fallback_questions IS 'Pre-seeded generic questions used as last-resort fallback when LLM generation fails.';


--
-- Name: generic_fallback_questions_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.generic_fallback_questions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.generic_fallback_questions_id_seq OWNER TO jithsungh;

--
-- Name: generic_fallback_questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.generic_fallback_questions_id_seq OWNED BY public.generic_fallback_questions.id;


--
-- Name: interview_exchanges; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_exchanges (
    id bigint NOT NULL,
    interview_submission_id bigint NOT NULL,
    sequence_order integer NOT NULL,
    question_id bigint,
    coding_problem_id bigint,
    question_text text NOT NULL,
    expected_answer text,
    difficulty_at_time public.difficulty_level NOT NULL,
    response_text text,
    response_code text,
    response_time_ms integer,
    ai_followup_message text,
    content_metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT interview_exchanges_check CHECK (((question_id IS NOT NULL) OR (coding_problem_id IS NOT NULL)))
);


ALTER TABLE public.interview_exchanges OWNER TO jithsungh;

--
-- Name: interview_exchanges_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.interview_exchanges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_exchanges_id_seq OWNER TO jithsungh;

--
-- Name: interview_exchanges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.interview_exchanges_id_seq OWNED BY public.interview_exchanges.id;


--
-- Name: interview_results; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_results (
    id bigint NOT NULL,
    interview_submission_id bigint NOT NULL,
    final_score numeric,
    normalized_score numeric,
    result_status text,
    recommendation text,
    scoring_version text NOT NULL,
    rubric_snapshot jsonb,
    template_weight_snapshot jsonb,
    section_scores jsonb,
    strengths text,
    weaknesses text,
    summary_notes text,
    generated_by text NOT NULL,
    model_id bigint,
    is_current boolean DEFAULT true NOT NULL,
    computed_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.interview_results OWNER TO jithsungh;

--
-- Name: interview_results_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.interview_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_results_id_seq OWNER TO jithsungh;

--
-- Name: interview_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.interview_results_id_seq OWNED BY public.interview_results.id;


--
-- Name: interview_submission_allowed_transitions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.interview_submission_allowed_transitions (
    from_status public.submission_status NOT NULL,
    to_status public.submission_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_interview_submission_allowed_transitions_no_self_loop CHECK ((from_status <> to_status))
);


ALTER TABLE public.interview_submission_allowed_transitions OWNER TO postgres;

--
-- Name: interview_submission_status_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.interview_submission_status_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_submission_status_audit_id_seq OWNER TO postgres;

--
-- Name: interview_submission_status_audit; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.interview_submission_status_audit (
    id bigint DEFAULT nextval('public.interview_submission_status_audit_id_seq'::regclass) NOT NULL,
    submission_id bigint NOT NULL,
    from_status public.submission_status NOT NULL,
    to_status public.submission_status NOT NULL,
    actor text,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.interview_submission_status_audit OWNER TO postgres;

--
-- Name: interview_submission_windows; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_submission_windows (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    admin_id bigint NOT NULL,
    name text NOT NULL,
    scope public.interview_scope NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    timezone text NOT NULL,
    max_allowed_submissions integer,
    allow_after_end_time boolean DEFAULT false NOT NULL,
    allow_resubmission boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT interview_submission_windows_check CHECK ((end_time > start_time))
);


ALTER TABLE public.interview_submission_windows OWNER TO jithsungh;

--
-- Name: interview_submission_windows_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.interview_submission_windows_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_submission_windows_id_seq OWNER TO jithsungh;

--
-- Name: interview_submission_windows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.interview_submission_windows_id_seq OWNED BY public.interview_submission_windows.id;


--
-- Name: interview_submissions; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_submissions (
    id bigint NOT NULL,
    candidate_id bigint NOT NULL,
    window_id bigint NOT NULL,
    role_id bigint NOT NULL,
    template_id bigint NOT NULL,
    mode public.interview_mode DEFAULT 'async'::public.interview_mode NOT NULL,
    status public.submission_status DEFAULT 'pending'::public.submission_status NOT NULL,
    final_score numeric,
    consent_captured boolean DEFAULT false NOT NULL,
    scheduled_start timestamp with time zone,
    scheduled_end timestamp with time zone,
    started_at timestamp with time zone,
    submitted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    current_exchange_sequence integer DEFAULT 0 NOT NULL,
    template_structure_snapshot jsonb,
    proctoring_risk_score numeric(6,2) DEFAULT 0.0,
    proctoring_risk_classification character varying(20),
    proctoring_flagged boolean DEFAULT false,
    proctoring_reviewed boolean DEFAULT false,
    version integer DEFAULT 1 NOT NULL,
    CONSTRAINT ck_submissions_exchange_sequence_non_negative CHECK ((current_exchange_sequence >= 0))
);


ALTER TABLE public.interview_submissions OWNER TO jithsungh;

--
-- Name: interview_submissions_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.interview_submissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_submissions_id_seq OWNER TO jithsungh;

--
-- Name: interview_submissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.interview_submissions_id_seq OWNED BY public.interview_submissions.id;


--
-- Name: interview_template_roles; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_template_roles (
    interview_template_id bigint NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.interview_template_roles OWNER TO jithsungh;

--
-- Name: interview_template_rubrics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_template_rubrics (
    id bigint NOT NULL,
    interview_template_id bigint NOT NULL,
    rubric_id bigint NOT NULL,
    section_name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.interview_template_rubrics OWNER TO jithsungh;

--
-- Name: interview_template_rubrics_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.interview_template_rubrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_template_rubrics_id_seq OWNER TO jithsungh;

--
-- Name: interview_template_rubrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.interview_template_rubrics_id_seq OWNED BY public.interview_template_rubrics.id;


--
-- Name: interview_templates; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.interview_templates (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    template_structure jsonb NOT NULL,
    rules jsonb,
    total_estimated_time_minutes integer,
    version integer DEFAULT 1 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.interview_templates OWNER TO jithsungh;

--
-- Name: interview_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.interview_templates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interview_templates_id_seq OWNER TO jithsungh;

--
-- Name: interview_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.interview_templates_id_seq OWNED BY public.interview_templates.id;


--
-- Name: job_descriptions; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.job_descriptions (
    id bigint NOT NULL,
    organization_id bigint NOT NULL,
    role_id bigint,
    title text NOT NULL,
    description_text text NOT NULL,
    requirements jsonb,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.job_descriptions OWNER TO jithsungh;

--
-- Name: job_descriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.job_descriptions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.job_descriptions_id_seq OWNER TO jithsungh;

--
-- Name: job_descriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.job_descriptions_id_seq OWNED BY public.job_descriptions.id;


--
-- Name: media_artifacts; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.media_artifacts (
    id bigint NOT NULL,
    interview_exchange_id bigint NOT NULL,
    media_type public.media_type NOT NULL,
    storage_uri text NOT NULL,
    duration_seconds integer,
    file_size_bytes bigint,
    captured_at timestamp with time zone NOT NULL,
    retention_expiry timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.media_artifacts OWNER TO jithsungh;

--
-- Name: media_artifacts_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.media_artifacts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.media_artifacts_id_seq OWNER TO jithsungh;

--
-- Name: media_artifacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.media_artifacts_id_seq OWNED BY public.media_artifacts.id;


--
-- Name: models; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.models (
    id bigint NOT NULL,
    provider text NOT NULL,
    name text NOT NULL,
    model_type text NOT NULL,
    version text,
    config jsonb,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.models OWNER TO jithsungh;

--
-- Name: models_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.models_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.models_id_seq OWNER TO jithsungh;

--
-- Name: models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.models_id_seq OWNED BY public.models.id;


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.organizations (
    id bigint NOT NULL,
    name text NOT NULL,
    organization_type public.organization_type NOT NULL,
    plan public.organization_plan DEFAULT 'free'::public.organization_plan NOT NULL,
    domain text,
    status public.organization_status DEFAULT 'active'::public.organization_status NOT NULL,
    policy_config jsonb,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.organizations OWNER TO jithsungh;

--
-- Name: organizations_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.organizations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.organizations_id_seq OWNER TO jithsungh;

--
-- Name: organizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.organizations_id_seq OWNED BY public.organizations.id;


--
-- Name: problem_language_templates; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.problem_language_templates (
    id bigint NOT NULL,
    problem_id bigint NOT NULL,
    language_id bigint NOT NULL,
    template_code text NOT NULL,
    entry_function text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    solution_code text
);


ALTER TABLE public.problem_language_templates OWNER TO jithsungh;

--
-- Name: COLUMN problem_language_templates.solution_code; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.problem_language_templates.solution_code IS 'Full working solution code for this problem in this language';


--
-- Name: problem_language_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

ALTER TABLE public.problem_language_templates ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.problem_language_templates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: proctoring_events; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.proctoring_events (
    id bigint NOT NULL,
    interview_submission_id bigint NOT NULL,
    event_type text NOT NULL,
    severity public.proctoring_severity NOT NULL,
    risk_weight numeric DEFAULT 1.0 NOT NULL,
    evidence jsonb NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.proctoring_events OWNER TO jithsungh;

--
-- Name: proctoring_events_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.proctoring_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.proctoring_events_id_seq OWNER TO jithsungh;

--
-- Name: proctoring_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.proctoring_events_id_seq OWNED BY public.proctoring_events.id;


--
-- Name: programming_languages; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.programming_languages (
    id bigint NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    version text,
    execution_environment text,
    is_active boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT programming_languages_slug_format CHECK ((slug ~ '^[a-z0-9_]+$'::text))
);


ALTER TABLE public.programming_languages OWNER TO jithsungh;

--
-- Name: programming_languages_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.programming_languages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.programming_languages_id_seq OWNER TO jithsungh;

--
-- Name: programming_languages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.programming_languages_id_seq OWNED BY public.programming_languages.id;


--
-- Name: prompt_templates; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.prompt_templates (
    id bigint NOT NULL,
    name text NOT NULL,
    prompt_type text NOT NULL,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    system_prompt text NOT NULL,
    user_prompt text NOT NULL,
    model_id bigint,
    model_config jsonb NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.prompt_templates OWNER TO jithsungh;

--
-- Name: prompt_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.prompt_templates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.prompt_templates_id_seq OWNER TO jithsungh;

--
-- Name: prompt_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.prompt_templates_id_seq OWNED BY public.prompt_templates.id;


--
-- Name: question_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.question_overrides_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.question_overrides_id_seq OWNER TO jithsungh;

--
-- Name: question_overrides; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.question_overrides (
    id bigint DEFAULT nextval('public.question_overrides_id_seq'::regclass) NOT NULL,
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.question_overrides OWNER TO jithsungh;

--
-- Name: TABLE question_overrides; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.question_overrides IS 'Tenant-specific overrides for super-org questions.';


--
-- Name: question_topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.question_topics (
    question_id bigint NOT NULL,
    topic_id bigint NOT NULL
);


ALTER TABLE public.question_topics OWNER TO jithsungh;

--
-- Name: questions; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.questions (
    id bigint NOT NULL,
    question_text text NOT NULL,
    answer_text text,
    question_type public.question_type NOT NULL,
    difficulty public.difficulty_level NOT NULL,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    source_type text,
    estimated_time_minutes integer DEFAULT 5 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.questions OWNER TO jithsungh;

--
-- Name: questions_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.questions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.questions_id_seq OWNER TO jithsungh;

--
-- Name: questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.questions_id_seq OWNED BY public.questions.id;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.refresh_tokens_id_seq OWNER TO jithsungh;

--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.refresh_tokens (
    id bigint DEFAULT nextval('public.refresh_tokens_id_seq'::regclass) NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    device_info text,
    ip_address inet,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    revoked_reason character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.refresh_tokens OWNER TO jithsungh;

--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.refresh_tokens IS 'Refresh tokens for JWT authentication. Tokens are hashed before storage.';


--
-- Name: COLUMN refresh_tokens.token_hash; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.refresh_tokens.token_hash IS 'SHA-256 hash of the refresh token. Original token never stored.';


--
-- Name: COLUMN refresh_tokens.revoked_at; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.refresh_tokens.revoked_at IS 'Timestamp when token was revoked. NULL means token is still active.';


--
-- Name: COLUMN refresh_tokens.revoked_reason; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.refresh_tokens.revoked_reason IS 'Reason for revocation: logout, password_change, admin_action, suspicious, rotation';


--
-- Name: resumes; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.resumes (
    id bigint NOT NULL,
    candidate_id bigint NOT NULL,
    file_url text NOT NULL,
    parsed_text text,
    extracted_data jsonb,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    file_name text,
    structured_json jsonb,
    llm_feedback jsonb,
    ats_score integer,
    ats_feedback text,
    embeddings jsonb,
    parse_status character varying(20) DEFAULT 'success'::character varying NOT NULL,
    llm_analysis_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    embeddings_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    parse_error text,
    llm_error text,
    embeddings_error text,
    analyzed_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.resumes OWNER TO jithsungh;

--
-- Name: resumes_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.resumes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.resumes_id_seq OWNER TO jithsungh;

--
-- Name: resumes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.resumes_id_seq OWNED BY public.resumes.id;


--
-- Name: role_coding_topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.role_coding_topics (
    role_id bigint NOT NULL,
    coding_topic_id bigint NOT NULL
);


ALTER TABLE public.role_coding_topics OWNER TO jithsungh;

--
-- Name: role_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.role_overrides_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.role_overrides_id_seq OWNER TO jithsungh;

--
-- Name: role_overrides; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.role_overrides (
    id bigint DEFAULT nextval('public.role_overrides_id_seq'::regclass) NOT NULL,
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.role_overrides OWNER TO jithsungh;

--
-- Name: TABLE role_overrides; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.role_overrides IS 'Tenant-specific overrides for super-org roles.';


--
-- Name: role_topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.role_topics (
    role_id bigint NOT NULL,
    topic_id bigint NOT NULL
);


ALTER TABLE public.role_topics OWNER TO jithsungh;

--
-- Name: roles; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.roles (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.roles OWNER TO jithsungh;

--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.roles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.roles_id_seq OWNER TO jithsungh;

--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: rubric_dimensions; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.rubric_dimensions (
    id bigint NOT NULL,
    rubric_id bigint NOT NULL,
    dimension_name text NOT NULL,
    description text,
    max_score numeric NOT NULL,
    weight numeric DEFAULT 1.0 NOT NULL,
    criteria jsonb,
    sequence_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.rubric_dimensions OWNER TO jithsungh;

--
-- Name: rubric_dimensions_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.rubric_dimensions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rubric_dimensions_id_seq OWNER TO jithsungh;

--
-- Name: rubric_dimensions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.rubric_dimensions_id_seq OWNED BY public.rubric_dimensions.id;


--
-- Name: rubric_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.rubric_overrides_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rubric_overrides_id_seq OWNER TO jithsungh;

--
-- Name: rubric_overrides; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.rubric_overrides (
    id bigint DEFAULT nextval('public.rubric_overrides_id_seq'::regclass) NOT NULL,
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.rubric_overrides OWNER TO jithsungh;

--
-- Name: TABLE rubric_overrides; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.rubric_overrides IS 'Tenant-specific overrides for super-org rubrics.';


--
-- Name: rubrics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.rubrics (
    id bigint NOT NULL,
    organization_id bigint,
    name text NOT NULL,
    description text,
    scope public.template_scope NOT NULL,
    schema jsonb,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.rubrics OWNER TO jithsungh;

--
-- Name: rubrics_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.rubrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rubrics_id_seq OWNER TO jithsungh;

--
-- Name: rubrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.rubrics_id_seq OWNED BY public.rubrics.id;


--
-- Name: source_topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.source_topics (
    id bigint NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    coding_topic_id bigint
);


ALTER TABLE public.source_topics OWNER TO jithsungh;

--
-- Name: source_topics_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.source_topics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.source_topics_id_seq OWNER TO jithsungh;

--
-- Name: source_topics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.source_topics_id_seq OWNED BY public.source_topics.id;


--
-- Name: supplementary_reports; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.supplementary_reports (
    id bigint NOT NULL,
    interview_submission_id bigint NOT NULL,
    report_type public.report_type NOT NULL,
    content jsonb NOT NULL,
    generated_by text NOT NULL,
    model_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.supplementary_reports OWNER TO jithsungh;

--
-- Name: supplementary_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.supplementary_reports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.supplementary_reports_id_seq OWNER TO jithsungh;

--
-- Name: supplementary_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.supplementary_reports_id_seq OWNED BY public.supplementary_reports.id;


--
-- Name: template_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.template_overrides_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.template_overrides_id_seq OWNER TO jithsungh;

--
-- Name: template_overrides; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.template_overrides (
    id bigint DEFAULT nextval('public.template_overrides_id_seq'::regclass) NOT NULL,
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.template_overrides OWNER TO jithsungh;

--
-- Name: TABLE template_overrides; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.template_overrides IS 'Tenant-specific overrides for super-org interview templates.';


--
-- Name: test_table; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.test_table (
);


ALTER TABLE public.test_table OWNER TO jithsungh;

--
-- Name: TABLE test_table; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.test_table IS 'test table for demonstration purpose';


--
-- Name: topic_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.topic_overrides_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.topic_overrides_id_seq OWNER TO jithsungh;

--
-- Name: topic_overrides; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.topic_overrides (
    id bigint DEFAULT nextval('public.topic_overrides_id_seq'::regclass) NOT NULL,
    organization_id bigint NOT NULL,
    base_content_id bigint NOT NULL,
    override_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.topic_overrides OWNER TO jithsungh;

--
-- Name: TABLE topic_overrides; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON TABLE public.topic_overrides IS 'Tenant-specific overrides for super-org topics.';


--
-- Name: topics; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.topics (
    id bigint NOT NULL,
    name text NOT NULL,
    description text,
    parent_topic_id bigint,
    scope public.template_scope NOT NULL,
    organization_id bigint,
    estimated_time_minutes integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.topics OWNER TO jithsungh;

--
-- Name: topics_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.topics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.topics_id_seq OWNER TO jithsungh;

--
-- Name: topics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.topics_id_seq OWNED BY public.topics.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    name text NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    status public.user_status DEFAULT 'active'::public.user_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_type character varying(20) NOT NULL,
    last_login_at timestamp with time zone,
    token_version integer DEFAULT 1 NOT NULL,
    CONSTRAINT users_user_type_check CHECK (((user_type)::text = ANY (ARRAY[('admin'::character varying)::text, ('candidate'::character varying)::text])))
);


ALTER TABLE public.users OWNER TO jithsungh;

--
-- Name: COLUMN users.user_type; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.users.user_type IS 'User type: admin or candidate. Determines which extended table (admins/candidates) contains additional data.';


--
-- Name: COLUMN users.last_login_at; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.users.last_login_at IS 'Timestamp of last successful login. Updated on each login event.';


--
-- Name: COLUMN users.token_version; Type: COMMENT; Schema: public; Owner: jithsungh
--

COMMENT ON COLUMN public.users.token_version IS 'Token version for forced logout. Incrementing this invalidates all active JWT tokens.';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO jithsungh;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: window_role_templates; Type: TABLE; Schema: public; Owner: jithsungh
--

CREATE TABLE public.window_role_templates (
    id bigint NOT NULL,
    window_id bigint NOT NULL,
    role_id bigint NOT NULL,
    template_id bigint NOT NULL,
    selection_weight integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.window_role_templates OWNER TO jithsungh;

--
-- Name: window_role_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: jithsungh
--

CREATE SEQUENCE public.window_role_templates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.window_role_templates_id_seq OWNER TO jithsungh;

--
-- Name: window_role_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jithsungh
--

ALTER SEQUENCE public.window_role_templates_id_seq OWNED BY public.window_role_templates.id;


--
-- Name: admins id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.admins ALTER COLUMN id SET DEFAULT nextval('public.admins_id_seq'::regclass);


--
-- Name: audio_analytics id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audio_analytics ALTER COLUMN id SET DEFAULT nextval('public.audio_analytics_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: candidate_career_insight_runs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_insight_runs ALTER COLUMN id SET DEFAULT nextval('public.candidate_career_insight_runs_id_seq'::regclass);


--
-- Name: candidate_career_roadmaps id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_roadmaps ALTER COLUMN id SET DEFAULT nextval('public.candidate_career_roadmaps_id_seq'::regclass);


--
-- Name: candidate_practice_deck_runs id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidate_practice_deck_runs ALTER COLUMN id SET DEFAULT nextval('public.candidate_practice_deck_runs_id_seq'::regclass);


--
-- Name: candidates id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidates ALTER COLUMN id SET DEFAULT nextval('public.candidates_id_seq'::regclass);


--
-- Name: code_execution_results id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_execution_results ALTER COLUMN id SET DEFAULT nextval('public.code_execution_results_id_seq'::regclass);


--
-- Name: code_submissions id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_submissions ALTER COLUMN id SET DEFAULT nextval('public.code_submissions_id_seq'::regclass);


--
-- Name: coding_problems id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problems ALTER COLUMN id SET DEFAULT nextval('public.coding_problems_id_seq'::regclass);


--
-- Name: coding_test_cases id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_test_cases ALTER COLUMN id SET DEFAULT nextval('public.coding_test_cases_id_seq'::regclass);


--
-- Name: coding_topics id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_topics ALTER COLUMN id SET DEFAULT nextval('public.coding_topics_id_seq'::regclass);


--
-- Name: difficulty_adaptation_log id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.difficulty_adaptation_log ALTER COLUMN id SET DEFAULT nextval('public.difficulty_adaptation_log_id_seq'::regclass);


--
-- Name: embeddings id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.embeddings ALTER COLUMN id SET DEFAULT nextval('public.embeddings_id_seq'::regclass);


--
-- Name: evaluation_dimension_scores id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluation_dimension_scores ALTER COLUMN id SET DEFAULT nextval('public.evaluation_dimension_scores_id_seq'::regclass);


--
-- Name: evaluations id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluations ALTER COLUMN id SET DEFAULT nextval('public.evaluations_id_seq'::regclass);


--
-- Name: generic_fallback_questions id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.generic_fallback_questions ALTER COLUMN id SET DEFAULT nextval('public.generic_fallback_questions_id_seq'::regclass);


--
-- Name: interview_exchanges id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_exchanges ALTER COLUMN id SET DEFAULT nextval('public.interview_exchanges_id_seq'::regclass);


--
-- Name: interview_results id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_results ALTER COLUMN id SET DEFAULT nextval('public.interview_results_id_seq'::regclass);


--
-- Name: interview_submission_windows id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submission_windows ALTER COLUMN id SET DEFAULT nextval('public.interview_submission_windows_id_seq'::regclass);


--
-- Name: interview_submissions id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submissions ALTER COLUMN id SET DEFAULT nextval('public.interview_submissions_id_seq'::regclass);


--
-- Name: interview_template_rubrics id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_rubrics ALTER COLUMN id SET DEFAULT nextval('public.interview_template_rubrics_id_seq'::regclass);


--
-- Name: interview_templates id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_templates ALTER COLUMN id SET DEFAULT nextval('public.interview_templates_id_seq'::regclass);


--
-- Name: job_descriptions id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.job_descriptions ALTER COLUMN id SET DEFAULT nextval('public.job_descriptions_id_seq'::regclass);


--
-- Name: media_artifacts id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.media_artifacts ALTER COLUMN id SET DEFAULT nextval('public.media_artifacts_id_seq'::regclass);


--
-- Name: models id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.models ALTER COLUMN id SET DEFAULT nextval('public.models_id_seq'::regclass);


--
-- Name: organizations id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.organizations ALTER COLUMN id SET DEFAULT nextval('public.organizations_id_seq'::regclass);


--
-- Name: proctoring_events id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.proctoring_events ALTER COLUMN id SET DEFAULT nextval('public.proctoring_events_id_seq'::regclass);


--
-- Name: programming_languages id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.programming_languages ALTER COLUMN id SET DEFAULT nextval('public.programming_languages_id_seq'::regclass);


--
-- Name: prompt_templates id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.prompt_templates ALTER COLUMN id SET DEFAULT nextval('public.prompt_templates_id_seq'::regclass);


--
-- Name: questions id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.questions ALTER COLUMN id SET DEFAULT nextval('public.questions_id_seq'::regclass);


--
-- Name: resumes id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.resumes ALTER COLUMN id SET DEFAULT nextval('public.resumes_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: rubric_dimensions id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_dimensions ALTER COLUMN id SET DEFAULT nextval('public.rubric_dimensions_id_seq'::regclass);


--
-- Name: rubrics id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubrics ALTER COLUMN id SET DEFAULT nextval('public.rubrics_id_seq'::regclass);


--
-- Name: source_topics id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.source_topics ALTER COLUMN id SET DEFAULT nextval('public.source_topics_id_seq'::regclass);


--
-- Name: supplementary_reports id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.supplementary_reports ALTER COLUMN id SET DEFAULT nextval('public.supplementary_reports_id_seq'::regclass);


--
-- Name: topics id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topics ALTER COLUMN id SET DEFAULT nextval('public.topics_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: window_role_templates id; Type: DEFAULT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.window_role_templates ALTER COLUMN id SET DEFAULT nextval('public.window_role_templates_id_seq'::regclass);


--
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (id);


--
-- Name: admins admins_user_id_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_user_id_organization_id_key UNIQUE (user_id, organization_id);


--
-- Name: audio_analytics audio_analytics_interview_exchange_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audio_analytics
    ADD CONSTRAINT audio_analytics_interview_exchange_id_key UNIQUE (interview_exchange_id);


--
-- Name: audio_analytics audio_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audio_analytics
    ADD CONSTRAINT audio_analytics_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: auth_audit_log auth_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.auth_audit_log
    ADD CONSTRAINT auth_audit_log_pkey PRIMARY KEY (id);


--
-- Name: candidate_career_insight_runs candidate_career_insight_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_insight_runs
    ADD CONSTRAINT candidate_career_insight_runs_pkey PRIMARY KEY (id);


--
-- Name: candidate_career_roadmaps candidate_career_roadmaps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_roadmaps
    ADD CONSTRAINT candidate_career_roadmaps_pkey PRIMARY KEY (id);


--
-- Name: candidate_practice_deck_runs candidate_practice_deck_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidate_practice_deck_runs
    ADD CONSTRAINT candidate_practice_deck_runs_pkey PRIMARY KEY (id);


--
-- Name: candidates candidates_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_pkey PRIMARY KEY (id);


--
-- Name: candidates candidates_user_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_user_id_key UNIQUE (user_id);


--
-- Name: code_execution_results code_execution_results_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_execution_results
    ADD CONSTRAINT code_execution_results_pkey PRIMARY KEY (id);


--
-- Name: code_submissions code_submissions_interview_exchange_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_submissions
    ADD CONSTRAINT code_submissions_interview_exchange_id_key UNIQUE (interview_exchange_id);


--
-- Name: code_submissions code_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_submissions
    ADD CONSTRAINT code_submissions_pkey PRIMARY KEY (id);


--
-- Name: coding_problem_overrides coding_problem_overrides_org_base_uq; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_overrides
    ADD CONSTRAINT coding_problem_overrides_org_base_uq UNIQUE (organization_id, base_content_id);


--
-- Name: coding_problem_overrides coding_problem_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_overrides
    ADD CONSTRAINT coding_problem_overrides_pkey PRIMARY KEY (id);


--
-- Name: coding_problem_topics coding_problem_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_topics
    ADD CONSTRAINT coding_problem_topics_pkey PRIMARY KEY (coding_problem_id, coding_topic_id);


--
-- Name: coding_problems coding_problems_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problems
    ADD CONSTRAINT coding_problems_pkey PRIMARY KEY (id);


--
-- Name: coding_test_cases coding_test_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_test_cases
    ADD CONSTRAINT coding_test_cases_pkey PRIMARY KEY (id);


--
-- Name: coding_topics coding_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_topics
    ADD CONSTRAINT coding_topics_pkey PRIMARY KEY (id);


--
-- Name: difficulty_adaptation_log difficulty_adaptation_log_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.difficulty_adaptation_log
    ADD CONSTRAINT difficulty_adaptation_log_pkey PRIMARY KEY (id);


--
-- Name: embeddings embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.embeddings
    ADD CONSTRAINT embeddings_pkey PRIMARY KEY (id);


--
-- Name: evaluation_dimension_scores evaluation_dimension_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluation_dimension_scores
    ADD CONSTRAINT evaluation_dimension_scores_pkey PRIMARY KEY (id);


--
-- Name: evaluations evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_pkey PRIMARY KEY (id);


--
-- Name: generic_fallback_questions generic_fallback_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.generic_fallback_questions
    ADD CONSTRAINT generic_fallback_questions_pkey PRIMARY KEY (id);


--
-- Name: interview_exchanges interview_exchanges_interview_submission_id_sequence_order_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_exchanges
    ADD CONSTRAINT interview_exchanges_interview_submission_id_sequence_order_key UNIQUE (interview_submission_id, sequence_order);


--
-- Name: interview_exchanges interview_exchanges_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_exchanges
    ADD CONSTRAINT interview_exchanges_pkey PRIMARY KEY (id);


--
-- Name: interview_results interview_results_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_results
    ADD CONSTRAINT interview_results_pkey PRIMARY KEY (id);


--
-- Name: interview_submission_allowed_transitions interview_submission_allowed_transitions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.interview_submission_allowed_transitions
    ADD CONSTRAINT interview_submission_allowed_transitions_pkey PRIMARY KEY (from_status, to_status);


--
-- Name: interview_submission_status_audit interview_submission_status_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.interview_submission_status_audit
    ADD CONSTRAINT interview_submission_status_audit_pkey PRIMARY KEY (id);


--
-- Name: interview_submission_windows interview_submission_windows_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submission_windows
    ADD CONSTRAINT interview_submission_windows_pkey PRIMARY KEY (id);


--
-- Name: interview_submissions interview_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submissions
    ADD CONSTRAINT interview_submissions_pkey PRIMARY KEY (id);


--
-- Name: interview_template_roles interview_template_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_roles
    ADD CONSTRAINT interview_template_roles_pkey PRIMARY KEY (interview_template_id, role_id);


--
-- Name: interview_template_rubrics interview_template_rubrics_interview_template_id_rubric_id__key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_rubrics
    ADD CONSTRAINT interview_template_rubrics_interview_template_id_rubric_id__key UNIQUE (interview_template_id, rubric_id, section_name);


--
-- Name: interview_template_rubrics interview_template_rubrics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_rubrics
    ADD CONSTRAINT interview_template_rubrics_pkey PRIMARY KEY (id);


--
-- Name: interview_templates interview_templates_name_version_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_templates
    ADD CONSTRAINT interview_templates_name_version_organization_id_key UNIQUE (name, version, organization_id);


--
-- Name: interview_templates interview_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_templates
    ADD CONSTRAINT interview_templates_pkey PRIMARY KEY (id);


--
-- Name: job_descriptions job_descriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.job_descriptions
    ADD CONSTRAINT job_descriptions_pkey PRIMARY KEY (id);


--
-- Name: media_artifacts media_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.media_artifacts
    ADD CONSTRAINT media_artifacts_pkey PRIMARY KEY (id);


--
-- Name: models models_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_pkey PRIMARY KEY (id);


--
-- Name: models models_provider_name_version_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_provider_name_version_key UNIQUE (provider, name, version);


--
-- Name: organizations organizations_domain_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_domain_key UNIQUE (domain);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: problem_language_templates problem_language_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.problem_language_templates
    ADD CONSTRAINT problem_language_templates_pkey PRIMARY KEY (id);


--
-- Name: proctoring_events proctoring_events_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.proctoring_events
    ADD CONSTRAINT proctoring_events_pkey PRIMARY KEY (id);


--
-- Name: programming_languages programming_languages_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.programming_languages
    ADD CONSTRAINT programming_languages_pkey PRIMARY KEY (id);


--
-- Name: programming_languages programming_languages_slug_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.programming_languages
    ADD CONSTRAINT programming_languages_slug_key UNIQUE (slug);


--
-- Name: prompt_templates prompt_templates_name_version_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_name_version_organization_id_key UNIQUE (name, version, organization_id);


--
-- Name: prompt_templates prompt_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_pkey PRIMARY KEY (id);


--
-- Name: question_overrides question_overrides_org_base_uq; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_overrides
    ADD CONSTRAINT question_overrides_org_base_uq UNIQUE (organization_id, base_content_id);


--
-- Name: question_overrides question_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_overrides
    ADD CONSTRAINT question_overrides_pkey PRIMARY KEY (id);


--
-- Name: question_topics question_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_topics
    ADD CONSTRAINT question_topics_pkey PRIMARY KEY (question_id, topic_id);


--
-- Name: questions questions_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_hash_unique; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_hash_unique UNIQUE (token_hash);


--
-- Name: resumes resumes_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.resumes
    ADD CONSTRAINT resumes_pkey PRIMARY KEY (id);


--
-- Name: role_coding_topics role_coding_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_coding_topics
    ADD CONSTRAINT role_coding_topics_pkey PRIMARY KEY (role_id, coding_topic_id);


--
-- Name: role_overrides role_overrides_org_base_uq; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_overrides
    ADD CONSTRAINT role_overrides_org_base_uq UNIQUE (organization_id, base_content_id);


--
-- Name: role_overrides role_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_overrides
    ADD CONSTRAINT role_overrides_pkey PRIMARY KEY (id);


--
-- Name: role_topics role_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_topics
    ADD CONSTRAINT role_topics_pkey PRIMARY KEY (role_id, topic_id);


--
-- Name: roles roles_name_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_organization_id_key UNIQUE (name, organization_id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: rubric_dimensions rubric_dimensions_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_dimensions
    ADD CONSTRAINT rubric_dimensions_pkey PRIMARY KEY (id);


--
-- Name: rubric_overrides rubric_overrides_org_base_uq; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_overrides
    ADD CONSTRAINT rubric_overrides_org_base_uq UNIQUE (organization_id, base_content_id);


--
-- Name: rubric_overrides rubric_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_overrides
    ADD CONSTRAINT rubric_overrides_pkey PRIMARY KEY (id);


--
-- Name: rubrics rubrics_name_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_name_organization_id_key UNIQUE (name, organization_id);


--
-- Name: rubrics rubrics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_pkey PRIMARY KEY (id);


--
-- Name: source_topics source_topics_name_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.source_topics
    ADD CONSTRAINT source_topics_name_key UNIQUE (name);


--
-- Name: source_topics source_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.source_topics
    ADD CONSTRAINT source_topics_pkey PRIMARY KEY (id);


--
-- Name: supplementary_reports supplementary_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.supplementary_reports
    ADD CONSTRAINT supplementary_reports_pkey PRIMARY KEY (id);


--
-- Name: template_overrides template_overrides_org_base_uq; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.template_overrides
    ADD CONSTRAINT template_overrides_org_base_uq UNIQUE (organization_id, base_content_id);


--
-- Name: template_overrides template_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.template_overrides
    ADD CONSTRAINT template_overrides_pkey PRIMARY KEY (id);


--
-- Name: topic_overrides topic_overrides_org_base_uq; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topic_overrides
    ADD CONSTRAINT topic_overrides_org_base_uq UNIQUE (organization_id, base_content_id);


--
-- Name: topic_overrides topic_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topic_overrides
    ADD CONSTRAINT topic_overrides_pkey PRIMARY KEY (id);


--
-- Name: topics topics_name_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_name_organization_id_key UNIQUE (name, organization_id);


--
-- Name: topics topics_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_pkey PRIMARY KEY (id);


--
-- Name: problem_language_templates uq_problem_language_template; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.problem_language_templates
    ADD CONSTRAINT uq_problem_language_template UNIQUE (problem_id, language_id);


--
-- Name: coding_problems uq_source_problem; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problems
    ADD CONSTRAINT uq_source_problem UNIQUE (source_name, source_id);


--
-- Name: code_execution_results uq_submission_test_case; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_execution_results
    ADD CONSTRAINT uq_submission_test_case UNIQUE (code_submission_id, test_case_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: window_role_templates window_role_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.window_role_templates
    ADD CONSTRAINT window_role_templates_pkey PRIMARY KEY (id);


--
-- Name: window_role_templates window_role_templates_window_id_role_id_template_id_key; Type: CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.window_role_templates
    ADD CONSTRAINT window_role_templates_window_id_role_id_template_id_key UNIQUE (window_id, role_id, template_id);


--
-- Name: idx_adaptation_log_created_at; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_adaptation_log_created_at ON public.difficulty_adaptation_log USING btree (created_at);


--
-- Name: idx_adaptation_log_submission; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_adaptation_log_submission ON public.difficulty_adaptation_log USING btree (submission_id);


--
-- Name: idx_admins_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_admins_org ON public.admins USING btree (organization_id);


--
-- Name: idx_admins_user; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_admins_user ON public.admins USING btree (user_id);


--
-- Name: idx_audio_analytics_exchange; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_audio_analytics_exchange ON public.audio_analytics USING btree (interview_exchange_id);


--
-- Name: idx_audio_analytics_finalized; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_audio_analytics_finalized ON public.audio_analytics USING btree (transcript_finalized);


--
-- Name: idx_audit_actor; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_audit_actor ON public.audit_logs USING btree (actor_user_id);


--
-- Name: idx_audit_created; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_audit_created ON public.audit_logs USING btree (created_at);


--
-- Name: idx_audit_entity; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_audit_entity ON public.audit_logs USING btree (entity_type, entity_id);


--
-- Name: idx_audit_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_audit_org ON public.audit_logs USING btree (organization_id);


--
-- Name: idx_auth_audit_created; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_auth_audit_created ON public.auth_audit_log USING btree (created_at);


--
-- Name: idx_auth_audit_event; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_auth_audit_event ON public.auth_audit_log USING btree (event_type);


--
-- Name: idx_auth_audit_ip; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_auth_audit_ip ON public.auth_audit_log USING btree (ip_address);


--
-- Name: idx_auth_audit_user; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_auth_audit_user ON public.auth_audit_log USING btree (user_id);


--
-- Name: idx_candidate_practice_deck_runs_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_candidate_practice_deck_runs_active ON public.candidate_practice_deck_runs USING btree (candidate_id, is_active, updated_at DESC);


--
-- Name: idx_candidate_practice_deck_runs_candidate_created; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_candidate_practice_deck_runs_candidate_created ON public.candidate_practice_deck_runs USING btree (candidate_id, created_at DESC);


--
-- Name: idx_candidate_practice_deck_runs_lookup; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_candidate_practice_deck_runs_lookup ON public.candidate_practice_deck_runs USING btree (candidate_id, role, industry, question_type, difficulty, created_at DESC);


--
-- Name: idx_candidates_user; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_candidates_user ON public.candidates USING btree (user_id);


--
-- Name: idx_career_insight_runs_candidate_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_career_insight_runs_candidate_created ON public.candidate_career_insight_runs USING btree (candidate_id, created_at DESC);


--
-- Name: idx_career_insight_runs_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_career_insight_runs_lookup ON public.candidate_career_insight_runs USING btree (candidate_id, industry, seniority, created_at DESC);


--
-- Name: idx_career_roadmaps_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_career_roadmaps_active ON public.candidate_career_roadmaps USING btree (candidate_id, is_active, updated_at DESC);


--
-- Name: idx_career_roadmaps_candidate_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_career_roadmaps_candidate_created ON public.candidate_career_roadmaps USING btree (candidate_id, created_at DESC);


--
-- Name: idx_code_execution_results_submission; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_code_execution_results_submission ON public.code_execution_results USING btree (code_submission_id);


--
-- Name: idx_code_submissions_status; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_code_submissions_status ON public.code_submissions USING btree (execution_status);


--
-- Name: idx_coding_problem_overrides_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problem_overrides_active ON public.coding_problem_overrides USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_coding_problem_overrides_base; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problem_overrides_base ON public.coding_problem_overrides USING btree (base_content_id);


--
-- Name: idx_coding_problem_overrides_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problem_overrides_org ON public.coding_problem_overrides USING btree (organization_id);


--
-- Name: idx_coding_problems_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problems_active ON public.coding_problems USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_coding_problems_difficulty; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problems_difficulty ON public.coding_problems USING btree (difficulty);


--
-- Name: idx_coding_problems_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problems_org ON public.coding_problems USING btree (organization_id);


--
-- Name: idx_coding_problems_pipeline_status; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_problems_pipeline_status ON public.coding_problems USING btree (pipeline_status);


--
-- Name: idx_coding_test_cases_problem; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_test_cases_problem ON public.coding_test_cases USING btree (coding_problem_id);


--
-- Name: idx_coding_topics_org_type; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_topics_org_type ON public.coding_topics USING btree (organization_id, topic_type);


--
-- Name: idx_coding_topics_roots; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_topics_roots ON public.coding_topics USING btree (organization_id, display_order) WHERE (parent_topic_id IS NULL);


--
-- Name: idx_coding_topics_tree; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_coding_topics_tree ON public.coding_topics USING btree (organization_id, parent_topic_id, display_order);


--
-- Name: idx_coding_topics_unique_sibling; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE UNIQUE INDEX idx_coding_topics_unique_sibling ON public.coding_topics USING btree (organization_id, parent_topic_id, name);


--
-- Name: idx_embeddings_model; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_embeddings_model ON public.embeddings USING btree (model_id);


--
-- Name: idx_embeddings_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_embeddings_org ON public.embeddings USING btree (organization_id);


--
-- Name: idx_embeddings_source; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_embeddings_source ON public.embeddings USING btree (source_type, source_id);


--
-- Name: idx_eval_dim_scores_evaluation; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_eval_dim_scores_evaluation ON public.evaluation_dimension_scores USING btree (evaluation_id);


--
-- Name: idx_evaluations_evaluated_by; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_evaluations_evaluated_by ON public.evaluations USING btree (evaluated_by) WHERE (evaluated_by IS NOT NULL);


--
-- Name: idx_evaluations_exchange; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_evaluations_exchange ON public.evaluations USING btree (interview_exchange_id);


--
-- Name: idx_evaluations_final; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_evaluations_final ON public.evaluations USING btree (is_final) WHERE (is_final = true);


--
-- Name: idx_evaluations_rubric; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_evaluations_rubric ON public.evaluations USING btree (rubric_id);


--
-- Name: idx_evaluations_scoring_version; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_evaluations_scoring_version ON public.evaluations USING btree (scoring_version) WHERE (scoring_version IS NOT NULL);


--
-- Name: idx_exchanges_coding; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_exchanges_coding ON public.interview_exchanges USING btree (coding_problem_id);


--
-- Name: idx_exchanges_question; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_exchanges_question ON public.interview_exchanges USING btree (question_id);


--
-- Name: idx_exchanges_sequence; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_exchanges_sequence ON public.interview_exchanges USING btree (interview_submission_id, sequence_order);


--
-- Name: idx_exchanges_submission; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_exchanges_submission ON public.interview_exchanges USING btree (interview_submission_id);


--
-- Name: idx_generic_fallback_diff_topic_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_generic_fallback_diff_topic_active ON public.generic_fallback_questions USING btree (difficulty, topic, is_active) WHERE (is_active = true);


--
-- Name: idx_generic_fallback_difficulty_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_generic_fallback_difficulty_active ON public.generic_fallback_questions USING btree (difficulty, usage_count) WHERE (is_active = true);


--
-- Name: idx_interview_results_computed; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_interview_results_computed ON public.interview_results USING btree (computed_at);


--
-- Name: idx_interview_results_current; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_interview_results_current ON public.interview_results USING btree (is_current) WHERE (is_current = true);


--
-- Name: idx_interview_results_status; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_interview_results_status ON public.interview_results USING btree (result_status);


--
-- Name: idx_interview_results_submission; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_interview_results_submission ON public.interview_results USING btree (interview_submission_id);


--
-- Name: idx_interview_results_submission_scoring_version; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_interview_results_submission_scoring_version ON public.interview_results USING btree (interview_submission_id, scoring_version);


--
-- Name: idx_interview_submission_status_audit_occurred; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_interview_submission_status_audit_occurred ON public.interview_submission_status_audit USING btree (occurred_at DESC);


--
-- Name: idx_interview_submission_status_audit_submission; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_interview_submission_status_audit_submission ON public.interview_submission_status_audit USING btree (submission_id, occurred_at DESC);


--
-- Name: idx_interview_submissions_expiry_scan; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_interview_submissions_expiry_scan ON public.interview_submissions USING btree (scheduled_end) WHERE (status = 'in_progress'::public.submission_status);


--
-- Name: idx_job_descriptions_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_job_descriptions_org ON public.job_descriptions USING btree (organization_id);


--
-- Name: idx_job_descriptions_role; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_job_descriptions_role ON public.job_descriptions USING btree (role_id);


--
-- Name: idx_media_artifacts_exchange; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_media_artifacts_exchange ON public.media_artifacts USING btree (interview_exchange_id);


--
-- Name: idx_plt_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_plt_active ON public.problem_language_templates USING btree (problem_id, language_id) WHERE (is_active = true);


--
-- Name: idx_plt_language; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_plt_language ON public.problem_language_templates USING btree (language_id) WHERE (is_active = true);


--
-- Name: idx_plt_problem; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_plt_problem ON public.problem_language_templates USING btree (problem_id) WHERE (is_active = true);


--
-- Name: idx_proctoring_events_occurred; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_proctoring_events_occurred ON public.proctoring_events USING btree (occurred_at);


--
-- Name: idx_proctoring_events_submission_occurred; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_proctoring_events_submission_occurred ON public.proctoring_events USING btree (interview_submission_id, occurred_at);


--
-- Name: idx_proctoring_severity; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_proctoring_severity ON public.proctoring_events USING btree (severity);


--
-- Name: idx_proctoring_submission; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_proctoring_submission ON public.proctoring_events USING btree (interview_submission_id);


--
-- Name: idx_programming_languages_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_programming_languages_active ON public.programming_languages USING btree (is_active);


--
-- Name: idx_prompt_templates_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_prompt_templates_active ON public.prompt_templates USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_prompt_templates_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_prompt_templates_org ON public.prompt_templates USING btree (organization_id);


--
-- Name: idx_prompt_templates_type; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_prompt_templates_type ON public.prompt_templates USING btree (prompt_type);


--
-- Name: idx_question_overrides_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_question_overrides_active ON public.question_overrides USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_question_overrides_base; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_question_overrides_base ON public.question_overrides USING btree (base_content_id);


--
-- Name: idx_question_overrides_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_question_overrides_org ON public.question_overrides USING btree (organization_id);


--
-- Name: idx_questions_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_questions_active ON public.questions USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_questions_difficulty; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_questions_difficulty ON public.questions USING btree (difficulty);


--
-- Name: idx_questions_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_questions_org ON public.questions USING btree (organization_id);


--
-- Name: idx_questions_scope; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_questions_scope ON public.questions USING btree (scope, organization_id);


--
-- Name: idx_questions_type; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_questions_type ON public.questions USING btree (question_type);


--
-- Name: idx_refresh_tokens_expires; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_refresh_tokens_expires ON public.refresh_tokens USING btree (expires_at) WHERE (revoked_at IS NULL);


--
-- Name: idx_refresh_tokens_revoked; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_refresh_tokens_revoked ON public.refresh_tokens USING btree (revoked_at) WHERE (revoked_at IS NOT NULL);


--
-- Name: idx_refresh_tokens_user; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_refresh_tokens_user ON public.refresh_tokens USING btree (user_id);


--
-- Name: idx_resumes_candidate; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_resumes_candidate ON public.resumes USING btree (candidate_id);


--
-- Name: idx_resumes_candidate_created_at; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_resumes_candidate_created_at ON public.resumes USING btree (candidate_id, created_at DESC);


--
-- Name: idx_role_overrides_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_role_overrides_active ON public.role_overrides USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_role_overrides_base; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_role_overrides_base ON public.role_overrides USING btree (base_content_id);


--
-- Name: idx_role_overrides_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_role_overrides_org ON public.role_overrides USING btree (organization_id);


--
-- Name: idx_roles_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_roles_org ON public.roles USING btree (organization_id);


--
-- Name: idx_rubric_dimensions_rubric; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_rubric_dimensions_rubric ON public.rubric_dimensions USING btree (rubric_id);


--
-- Name: idx_rubric_overrides_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_rubric_overrides_active ON public.rubric_overrides USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_rubric_overrides_base; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_rubric_overrides_base ON public.rubric_overrides USING btree (base_content_id);


--
-- Name: idx_rubric_overrides_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_rubric_overrides_org ON public.rubric_overrides USING btree (organization_id);


--
-- Name: idx_rubrics_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_rubrics_org ON public.rubrics USING btree (organization_id);


--
-- Name: idx_submissions_candidate; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_submissions_candidate ON public.interview_submissions USING btree (candidate_id);


--
-- Name: idx_submissions_created; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_submissions_created ON public.interview_submissions USING btree (created_at);


--
-- Name: idx_submissions_proctoring_flagged; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_submissions_proctoring_flagged ON public.interview_submissions USING btree (proctoring_flagged) WHERE (proctoring_flagged = true);


--
-- Name: idx_submissions_role; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_submissions_role ON public.interview_submissions USING btree (role_id);


--
-- Name: idx_submissions_status; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_submissions_status ON public.interview_submissions USING btree (status);


--
-- Name: idx_submissions_window; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_submissions_window ON public.interview_submissions USING btree (window_id);


--
-- Name: idx_supplementary_reports_submission; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_supplementary_reports_submission ON public.supplementary_reports USING btree (interview_submission_id);


--
-- Name: idx_supplementary_reports_type; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_supplementary_reports_type ON public.supplementary_reports USING btree (report_type);


--
-- Name: idx_template_overrides_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_template_overrides_active ON public.template_overrides USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_template_overrides_base; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_template_overrides_base ON public.template_overrides USING btree (base_content_id);


--
-- Name: idx_template_overrides_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_template_overrides_org ON public.template_overrides USING btree (organization_id);


--
-- Name: idx_templates_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_templates_active ON public.interview_templates USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_templates_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_templates_org ON public.interview_templates USING btree (organization_id);


--
-- Name: idx_topic_overrides_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_topic_overrides_active ON public.topic_overrides USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_topic_overrides_base; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_topic_overrides_base ON public.topic_overrides USING btree (base_content_id);


--
-- Name: idx_topic_overrides_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_topic_overrides_org ON public.topic_overrides USING btree (organization_id);


--
-- Name: idx_topics_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_topics_org ON public.topics USING btree (organization_id);


--
-- Name: idx_topics_parent; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_topics_parent ON public.topics USING btree (parent_topic_id);


--
-- Name: idx_users_last_login; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_users_last_login ON public.users USING btree (last_login_at) WHERE (last_login_at IS NOT NULL);


--
-- Name: idx_users_type; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_users_type ON public.users USING btree (user_type);


--
-- Name: idx_window_role_templates_role; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_window_role_templates_role ON public.window_role_templates USING btree (role_id);


--
-- Name: idx_window_role_templates_template; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_window_role_templates_template ON public.window_role_templates USING btree (template_id);


--
-- Name: idx_window_role_templates_window; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_window_role_templates_window ON public.window_role_templates USING btree (window_id);


--
-- Name: idx_windows_org; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_windows_org ON public.interview_submission_windows USING btree (organization_id);


--
-- Name: idx_windows_time; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE INDEX idx_windows_time ON public.interview_submission_windows USING btree (start_time, end_time);


--
-- Name: uq_candidate_practice_deck_runs_one_active; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE UNIQUE INDEX uq_candidate_practice_deck_runs_one_active ON public.candidate_practice_deck_runs USING btree (candidate_id) WHERE (is_active = true);


--
-- Name: uq_candidate_window_role_non_practice; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE UNIQUE INDEX uq_candidate_window_role_non_practice ON public.interview_submissions USING btree (candidate_id, window_id, role_id) WHERE (window_id <> 86);


--
-- Name: uq_career_roadmaps_one_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_career_roadmaps_one_active ON public.candidate_career_roadmaps USING btree (candidate_id) WHERE (is_active = true);


--
-- Name: uq_evaluations_exchange_final; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE UNIQUE INDEX uq_evaluations_exchange_final ON public.evaluations USING btree (interview_exchange_id) WHERE (is_final = true);


--
-- Name: uq_interview_results_submission_current; Type: INDEX; Schema: public; Owner: jithsungh
--

CREATE UNIQUE INDEX uq_interview_results_submission_current ON public.interview_results USING btree (interview_submission_id) WHERE (is_current = true);


--
-- Name: interview_submissions trg_audit_interview_submission_status_transition; Type: TRIGGER; Schema: public; Owner: jithsungh
--

CREATE TRIGGER trg_audit_interview_submission_status_transition AFTER UPDATE OF status ON public.interview_submissions FOR EACH ROW EXECUTE FUNCTION public.fn_audit_interview_submission_status_transition();


--
-- Name: interview_submissions trg_validate_interview_submission_status_transition; Type: TRIGGER; Schema: public; Owner: jithsungh
--

CREATE TRIGGER trg_validate_interview_submission_status_transition BEFORE UPDATE OF status ON public.interview_submissions FOR EACH ROW EXECUTE FUNCTION public.fn_validate_interview_submission_status_transition();


--
-- Name: admins admins_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: admins admins_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: audio_analytics audio_analytics_interview_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audio_analytics
    ADD CONSTRAINT audio_analytics_interview_exchange_id_fkey FOREIGN KEY (interview_exchange_id) REFERENCES public.interview_exchanges(id) ON DELETE CASCADE;


--
-- Name: audit_logs audit_logs_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: audit_logs audit_logs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: auth_audit_log auth_audit_log_user_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.auth_audit_log
    ADD CONSTRAINT auth_audit_log_user_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: candidate_career_insight_runs candidate_career_insight_runs_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_insight_runs
    ADD CONSTRAINT candidate_career_insight_runs_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id) ON DELETE CASCADE;


--
-- Name: candidate_career_roadmaps candidate_career_roadmaps_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_roadmaps
    ADD CONSTRAINT candidate_career_roadmaps_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id) ON DELETE CASCADE;


--
-- Name: candidate_career_roadmaps candidate_career_roadmaps_insight_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.candidate_career_roadmaps
    ADD CONSTRAINT candidate_career_roadmaps_insight_run_id_fkey FOREIGN KEY (insight_run_id) REFERENCES public.candidate_career_insight_runs(id) ON DELETE SET NULL;


--
-- Name: candidate_practice_deck_runs candidate_practice_deck_runs_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidate_practice_deck_runs
    ADD CONSTRAINT candidate_practice_deck_runs_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id) ON DELETE CASCADE;


--
-- Name: candidates candidates_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: code_execution_results code_execution_results_code_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_execution_results
    ADD CONSTRAINT code_execution_results_code_submission_id_fkey FOREIGN KEY (code_submission_id) REFERENCES public.code_submissions(id) ON DELETE CASCADE;


--
-- Name: code_execution_results code_execution_results_test_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_execution_results
    ADD CONSTRAINT code_execution_results_test_case_id_fkey FOREIGN KEY (test_case_id) REFERENCES public.coding_test_cases(id) ON DELETE CASCADE;


--
-- Name: code_submissions code_submissions_coding_problem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_submissions
    ADD CONSTRAINT code_submissions_coding_problem_id_fkey FOREIGN KEY (coding_problem_id) REFERENCES public.coding_problems(id) ON DELETE CASCADE;


--
-- Name: code_submissions code_submissions_interview_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.code_submissions
    ADD CONSTRAINT code_submissions_interview_exchange_id_fkey FOREIGN KEY (interview_exchange_id) REFERENCES public.interview_exchanges(id) ON DELETE CASCADE;


--
-- Name: coding_problem_overrides coding_problem_overrides_base_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_overrides
    ADD CONSTRAINT coding_problem_overrides_base_content_id_fkey FOREIGN KEY (base_content_id) REFERENCES public.coding_problems(id) ON DELETE CASCADE;


--
-- Name: coding_problem_overrides coding_problem_overrides_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_overrides
    ADD CONSTRAINT coding_problem_overrides_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: coding_problem_topics coding_problem_topics_coding_problem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_topics
    ADD CONSTRAINT coding_problem_topics_coding_problem_id_fkey FOREIGN KEY (coding_problem_id) REFERENCES public.coding_problems(id) ON DELETE CASCADE;


--
-- Name: coding_problem_topics coding_problem_topics_coding_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problem_topics
    ADD CONSTRAINT coding_problem_topics_coding_topic_id_fkey FOREIGN KEY (coding_topic_id) REFERENCES public.coding_topics(id) ON DELETE CASCADE;


--
-- Name: coding_problems coding_problems_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_problems
    ADD CONSTRAINT coding_problems_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: coding_test_cases coding_test_cases_coding_problem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_test_cases
    ADD CONSTRAINT coding_test_cases_coding_problem_id_fkey FOREIGN KEY (coding_problem_id) REFERENCES public.coding_problems(id) ON DELETE CASCADE;


--
-- Name: coding_topics coding_topics_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_topics
    ADD CONSTRAINT coding_topics_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: coding_topics coding_topics_parent_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.coding_topics
    ADD CONSTRAINT coding_topics_parent_topic_id_fkey FOREIGN KEY (parent_topic_id) REFERENCES public.coding_topics(id) ON DELETE SET NULL;


--
-- Name: embeddings embeddings_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.embeddings
    ADD CONSTRAINT embeddings_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id) ON DELETE CASCADE;


--
-- Name: embeddings embeddings_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.embeddings
    ADD CONSTRAINT embeddings_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: evaluation_dimension_scores evaluation_dimension_scores_evaluation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluation_dimension_scores
    ADD CONSTRAINT evaluation_dimension_scores_evaluation_id_fkey FOREIGN KEY (evaluation_id) REFERENCES public.evaluations(id) ON DELETE CASCADE;


--
-- Name: evaluation_dimension_scores evaluation_dimension_scores_rubric_dimension_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluation_dimension_scores
    ADD CONSTRAINT evaluation_dimension_scores_rubric_dimension_id_fkey FOREIGN KEY (rubric_dimension_id) REFERENCES public.rubric_dimensions(id) ON DELETE CASCADE;


--
-- Name: evaluations evaluations_evaluated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_evaluated_by_fkey FOREIGN KEY (evaluated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: evaluations evaluations_interview_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_interview_exchange_id_fkey FOREIGN KEY (interview_exchange_id) REFERENCES public.interview_exchanges(id) ON DELETE CASCADE;


--
-- Name: evaluations evaluations_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE SET NULL;


--
-- Name: evaluations fk_evaluations_model; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT fk_evaluations_model FOREIGN KEY (model_id) REFERENCES public.models(id) ON DELETE SET NULL;


--
-- Name: problem_language_templates fk_plt_language; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.problem_language_templates
    ADD CONSTRAINT fk_plt_language FOREIGN KEY (language_id) REFERENCES public.programming_languages(id) ON DELETE CASCADE;


--
-- Name: problem_language_templates fk_plt_problem; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.problem_language_templates
    ADD CONSTRAINT fk_plt_problem FOREIGN KEY (problem_id) REFERENCES public.coding_problems(id) ON DELETE CASCADE;


--
-- Name: source_topics fk_source_topics_coding_topic; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.source_topics
    ADD CONSTRAINT fk_source_topics_coding_topic FOREIGN KEY (coding_topic_id) REFERENCES public.coding_topics(id) ON DELETE RESTRICT;


--
-- Name: interview_exchanges interview_exchanges_coding_problem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_exchanges
    ADD CONSTRAINT interview_exchanges_coding_problem_id_fkey FOREIGN KEY (coding_problem_id) REFERENCES public.coding_problems(id) ON DELETE SET NULL;


--
-- Name: interview_exchanges interview_exchanges_interview_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_exchanges
    ADD CONSTRAINT interview_exchanges_interview_submission_id_fkey FOREIGN KEY (interview_submission_id) REFERENCES public.interview_submissions(id) ON DELETE CASCADE;


--
-- Name: interview_exchanges interview_exchanges_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_exchanges
    ADD CONSTRAINT interview_exchanges_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.questions(id) ON DELETE SET NULL;


--
-- Name: interview_results interview_results_interview_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_results
    ADD CONSTRAINT interview_results_interview_submission_id_fkey FOREIGN KEY (interview_submission_id) REFERENCES public.interview_submissions(id) ON DELETE CASCADE;


--
-- Name: interview_results interview_results_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_results
    ADD CONSTRAINT interview_results_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id) ON DELETE SET NULL;


--
-- Name: interview_submission_status_audit interview_submission_status_audit_submission_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.interview_submission_status_audit
    ADD CONSTRAINT interview_submission_status_audit_submission_fkey FOREIGN KEY (submission_id) REFERENCES public.interview_submissions(id) ON DELETE CASCADE;


--
-- Name: interview_submission_windows interview_submission_windows_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submission_windows
    ADD CONSTRAINT interview_submission_windows_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(id);


--
-- Name: interview_submission_windows interview_submission_windows_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submission_windows
    ADD CONSTRAINT interview_submission_windows_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: interview_submissions interview_submissions_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submissions
    ADD CONSTRAINT interview_submissions_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id) ON DELETE CASCADE;


--
-- Name: interview_submissions interview_submissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submissions
    ADD CONSTRAINT interview_submissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: interview_submissions interview_submissions_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submissions
    ADD CONSTRAINT interview_submissions_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.interview_templates(id) ON DELETE CASCADE;


--
-- Name: interview_submissions interview_submissions_window_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_submissions
    ADD CONSTRAINT interview_submissions_window_id_fkey FOREIGN KEY (window_id) REFERENCES public.interview_submission_windows(id) ON DELETE CASCADE;


--
-- Name: interview_template_roles interview_template_roles_interview_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_roles
    ADD CONSTRAINT interview_template_roles_interview_template_id_fkey FOREIGN KEY (interview_template_id) REFERENCES public.interview_templates(id) ON DELETE CASCADE;


--
-- Name: interview_template_roles interview_template_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_roles
    ADD CONSTRAINT interview_template_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: interview_template_rubrics interview_template_rubrics_interview_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_rubrics
    ADD CONSTRAINT interview_template_rubrics_interview_template_id_fkey FOREIGN KEY (interview_template_id) REFERENCES public.interview_templates(id) ON DELETE CASCADE;


--
-- Name: interview_template_rubrics interview_template_rubrics_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_template_rubrics
    ADD CONSTRAINT interview_template_rubrics_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: interview_templates interview_templates_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.interview_templates
    ADD CONSTRAINT interview_templates_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: job_descriptions job_descriptions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.job_descriptions
    ADD CONSTRAINT job_descriptions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: job_descriptions job_descriptions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.job_descriptions
    ADD CONSTRAINT job_descriptions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE SET NULL;


--
-- Name: media_artifacts media_artifacts_interview_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.media_artifacts
    ADD CONSTRAINT media_artifacts_interview_exchange_id_fkey FOREIGN KEY (interview_exchange_id) REFERENCES public.interview_exchanges(id) ON DELETE CASCADE;


--
-- Name: proctoring_events proctoring_events_interview_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.proctoring_events
    ADD CONSTRAINT proctoring_events_interview_submission_id_fkey FOREIGN KEY (interview_submission_id) REFERENCES public.interview_submissions(id) ON DELETE CASCADE;


--
-- Name: prompt_templates prompt_templates_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id) ON DELETE SET NULL;


--
-- Name: prompt_templates prompt_templates_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: question_overrides question_overrides_base_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_overrides
    ADD CONSTRAINT question_overrides_base_content_id_fkey FOREIGN KEY (base_content_id) REFERENCES public.questions(id) ON DELETE CASCADE;


--
-- Name: question_overrides question_overrides_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_overrides
    ADD CONSTRAINT question_overrides_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: question_topics question_topics_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_topics
    ADD CONSTRAINT question_topics_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.questions(id) ON DELETE CASCADE;


--
-- Name: question_topics question_topics_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.question_topics
    ADD CONSTRAINT question_topics_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES public.topics(id) ON DELETE CASCADE;


--
-- Name: questions questions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_user_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: resumes resumes_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.resumes
    ADD CONSTRAINT resumes_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id) ON DELETE CASCADE;


--
-- Name: role_coding_topics role_coding_topics_coding_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_coding_topics
    ADD CONSTRAINT role_coding_topics_coding_topic_id_fkey FOREIGN KEY (coding_topic_id) REFERENCES public.coding_topics(id) ON DELETE CASCADE;


--
-- Name: role_coding_topics role_coding_topics_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_coding_topics
    ADD CONSTRAINT role_coding_topics_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_overrides role_overrides_base_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_overrides
    ADD CONSTRAINT role_overrides_base_content_id_fkey FOREIGN KEY (base_content_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_overrides role_overrides_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_overrides
    ADD CONSTRAINT role_overrides_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: role_topics role_topics_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_topics
    ADD CONSTRAINT role_topics_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_topics role_topics_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.role_topics
    ADD CONSTRAINT role_topics_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES public.topics(id) ON DELETE CASCADE;


--
-- Name: roles roles_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: rubric_dimensions rubric_dimensions_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_dimensions
    ADD CONSTRAINT rubric_dimensions_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: rubric_overrides rubric_overrides_base_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_overrides
    ADD CONSTRAINT rubric_overrides_base_content_id_fkey FOREIGN KEY (base_content_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: rubric_overrides rubric_overrides_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubric_overrides
    ADD CONSTRAINT rubric_overrides_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: rubrics rubrics_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: supplementary_reports supplementary_reports_interview_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.supplementary_reports
    ADD CONSTRAINT supplementary_reports_interview_submission_id_fkey FOREIGN KEY (interview_submission_id) REFERENCES public.interview_submissions(id) ON DELETE CASCADE;


--
-- Name: supplementary_reports supplementary_reports_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.supplementary_reports
    ADD CONSTRAINT supplementary_reports_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id) ON DELETE SET NULL;


--
-- Name: template_overrides template_overrides_base_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.template_overrides
    ADD CONSTRAINT template_overrides_base_content_id_fkey FOREIGN KEY (base_content_id) REFERENCES public.interview_templates(id) ON DELETE CASCADE;


--
-- Name: template_overrides template_overrides_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.template_overrides
    ADD CONSTRAINT template_overrides_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: topic_overrides topic_overrides_base_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topic_overrides
    ADD CONSTRAINT topic_overrides_base_content_id_fkey FOREIGN KEY (base_content_id) REFERENCES public.topics(id) ON DELETE CASCADE;


--
-- Name: topic_overrides topic_overrides_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topic_overrides
    ADD CONSTRAINT topic_overrides_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: topics topics_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: topics topics_parent_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_parent_topic_id_fkey FOREIGN KEY (parent_topic_id) REFERENCES public.topics(id) ON DELETE SET NULL;


--
-- Name: window_role_templates window_role_templates_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.window_role_templates
    ADD CONSTRAINT window_role_templates_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: window_role_templates window_role_templates_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.window_role_templates
    ADD CONSTRAINT window_role_templates_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.interview_templates(id) ON DELETE CASCADE;


--
-- Name: window_role_templates window_role_templates_window_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jithsungh
--

ALTER TABLE ONLY public.window_role_templates
    ADD CONSTRAINT window_role_templates_window_id_fkey FOREIGN KEY (window_id) REFERENCES public.interview_submission_windows(id) ON DELETE CASCADE;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO jithsungh;
GRANT ALL ON SCHEMA public TO jayanadh;
GRANT ALL ON SCHEMA public TO vysali;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: jithsungh
--

ALTER DEFAULT PRIVILEGES FOR ROLE jithsungh IN SCHEMA public GRANT SELECT ON TABLES TO jithsungh;


--
-- PostgreSQL database dump complete
--

\unrestrict 8q91naVy8neIQ4clJuUYcglOmRD3MVVGTwJSCZfKRIXTayzG9cSFNq80OzhKct2

