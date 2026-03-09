--
-- Migration DEV-50: Populate Rubrics and Rubric Dimensions
--
-- Purpose: Seed the rubrics and rubric_dimensions tables with evaluation
--          criteria used by the AI scoring pipeline. Also maps rubrics to
--          interview templates via interview_template_rubrics.
-- Date: 2026-03-09
-- Module: app/evaluation
-- Ticket: DEV-50
--
-- Changes:
--   1. Insert 2 rubrics: General Technical Interview, Backend Engineer
--   2. Insert rubric dimensions for each rubric
--   3. Map rubrics to interview templates via interview_template_rubrics
--
-- Design:
--   Rubric 1 (General Technical Interview):
--     A universal rubric covering all question types in a standard interview —
--     self-introduction, technical Q&A, coding, and complexity analysis.
--     Dimensions: Communication, Technical Accuracy, Depth of Knowledge,
--     Problem Solving, Code Quality, Efficiency, Explanation Clarity.
--
--   Rubric 2 (Backend Engineer):
--     Role-specific rubric for backend engineering roles. Adds dimensions
--     for system design, API design, database knowledge, and trade-off
--     analysis while retaining core coding and communication dimensions.
--
-- Dimension names are sourced from frontend mock data expectations
-- (data/frontend_mock_data/candidateMockData.ts) to ensure the AI
-- evaluator's scored dimensions match what the UI renders.
--
-- Invariants preserved:
--   - All rubrics have scope='public' (available to all organizations)
--   - Rubric IDs are explicit (1-2) for deterministic references
--   - Dimension IDs are explicit (1-17) for deterministic FK references
--   - interview_template_rubrics maps existing templates (IDs 1-6)
--   - No SRS invariant broken (populating existing tables)
--   - No ERD invariant violated (valid FK relationships)
--
-- Rollback: See DEV-50_populate-rubrics-and-dimensions_rollback.sql
--

-- ============================================================================
-- PART 1: Rubrics
-- ============================================================================

INSERT INTO public.rubrics (id, name, description, scope, organization_id, schema, is_active)
VALUES

-- --------------------------------------------------------------------------
-- Rubric 1: General Technical Interview
-- --------------------------------------------------------------------------
(1,
 'General Technical Interview',
 'Universal rubric for standard technical interviews. Covers self-introduction, '
 'technical knowledge, coding, and complexity analysis sections. Suitable for '
 'all roles and experience levels.',
 'public', NULL,
 '{
    "version": "1.0",
    "total_sections": 4,
    "sections": ["Self Introduction", "Technical", "Coding", "Complexity Analysis"],
    "scoring_method": "weighted_average",
    "pass_threshold": 60,
    "recommendation_thresholds": {
      "strong_hire": 85,
      "hire": 70,
      "borderline": 55,
      "no_hire": 0
    }
  }',
 true),

-- --------------------------------------------------------------------------
-- Rubric 2: Backend Engineer (Role-Specific)
-- --------------------------------------------------------------------------
(2,
 'Backend Engineer',
 'Role-specific rubric for backend engineering candidates. Emphasises system '
 'design, API design, database knowledge, and scalability trade-offs in '
 'addition to core coding and communication skills.',
 'public', NULL,
 '{
    "version": "1.0",
    "total_sections": 4,
    "sections": ["Self Introduction", "Technical", "Coding", "Complexity Analysis"],
    "scoring_method": "weighted_average",
    "pass_threshold": 60,
    "target_role": "Backend Engineer",
    "recommendation_thresholds": {
      "strong_hire": 85,
      "hire": 70,
      "borderline": 55,
      "no_hire": 0
    }
  }',
 true)

ON CONFLICT (id) DO NOTHING;

-- Reset sequence past the last explicit ID
SELECT setval('public.rubrics_id_seq', GREATEST(
  (SELECT COALESCE(MAX(id), 0) FROM public.rubrics), 2
));


-- ============================================================================
-- PART 2: Rubric Dimensions — General Technical Interview (rubric_id = 1)
-- ============================================================================

INSERT INTO public.rubric_dimensions
    (id, rubric_id, dimension_name, description, max_score, weight, criteria, sequence_order)
VALUES

-- Self-Introduction dimensions
(1, 1, 'Communication',
 'Clarity, articulation, and confidence in verbal responses. '
 'Evaluates structure of delivery and ability to convey ideas concisely.',
 10.0, 1.0,
 '{"criteria_text": "0-3: Incoherent or very unclear. 4-5: Basic communication with frequent hesitation. 6-7: Clear communication with minor gaps. 8-9: Strong, well-structured delivery. 10: Exceptional clarity, conciseness, and confidence.", "applies_to": "self_introduction"}',
 1),

(2, 1, 'Structure',
 'Logical flow and organisation of the response. '
 'Evaluates whether the candidate presents a coherent narrative.',
 10.0, 0.8,
 '{"criteria_text": "0-3: No discernible structure. 4-5: Loosely organised. 6-7: Good logical flow with minor jumps. 8-9: Well-structured with clear progression. 10: Exemplary narrative arc.", "applies_to": "self_introduction"}',
 2),

(3, 1, 'Confidence',
 'Poise and self-assurance during responses. '
 'Not arrogance, but comfortable command of the conversation.',
 10.0, 0.6,
 '{"criteria_text": "0-3: Very nervous or disengaged. 4-5: Some hesitation but generally present. 6-7: Reasonably confident. 8-9: Composed and self-assured. 10: Naturally commanding without arrogance.", "applies_to": "self_introduction"}',
 3),

-- Technical Q&A dimensions
(4, 1, 'Technical Accuracy',
 'Correctness and precision of technical explanations. '
 'Evaluates factual accuracy and understanding of concepts.',
 10.0, 1.5,
 '{"criteria_text": "0-3: Fundamentally incorrect. 4-5: Partially correct with significant gaps. 6-7: Mostly correct with minor inaccuracies. 8-9: Accurate and precise. 10: Expert-level accuracy with nuanced understanding.", "applies_to": "technical"}',
 4),

(5, 1, 'Depth of Knowledge',
 'Breadth and depth of understanding beyond surface-level answers. '
 'Evaluates ability to reason about edge cases, alternatives, and implications.',
 10.0, 1.2,
 '{"criteria_text": "0-3: Surface-level only. 4-5: Some depth on basics. 6-7: Good depth with awareness of trade-offs. 8-9: Deep understanding with edge-case reasoning. 10: Exceptional depth, cites internals and research-level insights.", "applies_to": "technical"}',
 5),

-- Coding dimensions
(6, 1, 'Correctness',
 'Whether the code produces the expected output for all inputs, '
 'including edge cases and boundary conditions.',
 10.0, 1.5,
 '{"criteria_text": "0-3: Does not compile/run or produces wrong output. 4-5: Works for basic cases, fails on edge cases. 6-7: Handles most cases correctly. 8-9: All test cases pass. 10: Provably correct with edge case handling.", "applies_to": "coding"}',
 6),

(7, 1, 'Code Quality',
 'Readability, naming conventions, modularity, and idiomatic usage '
 'of the chosen language.',
 10.0, 1.0,
 '{"criteria_text": "0-3: Unreadable or spaghetti code. 4-5: Works but poorly structured. 6-7: Reasonable readability. 8-9: Clean, idiomatic code with good naming. 10: Production-grade quality, proper abstraction.", "applies_to": "coding"}',
 7),

(8, 1, 'Efficiency',
 'Time and space complexity of the solution. '
 'Evaluates optimality and awareness of performance characteristics.',
 10.0, 1.2,
 '{"criteria_text": "0-3: Brute force with no optimisation awareness. 4-5: Sub-optimal but functional. 6-7: Reasonable complexity, aware of better approaches. 8-9: Optimal solution. 10: Optimal with clear justification of complexity bounds.", "applies_to": "coding"}',
 8),

-- Complexity Analysis dimensions
(9, 1, 'Accuracy',
 'Correctness of time and space complexity analysis. '
 'Evaluates whether the candidate correctly identifies Big-O bounds.',
 10.0, 1.0,
 '{"criteria_text": "0-3: Completely wrong analysis. 4-5: Partially correct. 6-7: Correct Big-O but weak justification. 8-9: Correct with solid reasoning. 10: Correct with amortised/worst-case distinction where applicable.", "applies_to": "complexity_analysis"}',
 9),

(10, 1, 'Explanation Clarity',
 'Ability to explain complexity reasoning in a clear, '
 'step-by-step manner that demonstrates genuine understanding.',
 10.0, 0.8,
 '{"criteria_text": "0-3: Cannot explain. 4-5: Vague or memorised explanation. 6-7: Reasonable explanation. 8-9: Clear, step-by-step walkthrough. 10: Teaches the concept while explaining their solution.", "applies_to": "complexity_analysis"}',
 10)

ON CONFLICT (id) DO NOTHING;


-- ============================================================================
-- PART 3: Rubric Dimensions — Backend Engineer (rubric_id = 2)
-- ============================================================================

INSERT INTO public.rubric_dimensions
    (id, rubric_id, dimension_name, description, max_score, weight, criteria, sequence_order)
VALUES

-- Core dimensions (shared conceptually, but tuned for backend)
(11, 2, 'Technical Accuracy',
 'Correctness and depth of backend-specific technical knowledge: '
 'APIs, databases, concurrency, caching, message queues.',
 10.0, 1.5,
 '{"criteria_text": "0-3: Fundamental misunderstandings. 4-5: Basic awareness but gaps in core backend concepts. 6-7: Solid understanding of REST, SQL, and server-side patterns. 8-9: Expert-level backend knowledge. 10: Demonstrates deep internals knowledge (query planners, connection pooling, etc.).", "applies_to": "technical"}',
 1),

(12, 2, 'System Thinking',
 'Ability to reason about distributed systems, scalability, '
 'fault tolerance, and end-to-end request flows.',
 10.0, 1.5,
 '{"criteria_text": "0-3: No systems awareness. 4-5: Basic client-server understanding. 6-7: Can design a simple distributed system. 8-9: Strong systems reasoning with CAP/PACELC trade-offs. 10: Architect-level thinking with cross-cutting concerns.", "applies_to": "system_design"}',
 2),

(13, 2, 'Trade-off Analysis',
 'Ability to evaluate and articulate engineering trade-offs: '
 'consistency vs availability, latency vs throughput, SQL vs NoSQL.',
 10.0, 1.2,
 '{"criteria_text": "0-3: Picks solutions without justification. 4-5: Acknowledges trade-offs but cannot articulate them. 6-7: Discusses 2-3 trade-offs with reasoning. 8-9: Systematic trade-off analysis with data-informed decisions. 10: Nuanced multi-dimensional trade-off evaluation.", "applies_to": "system_design"}',
 3),

(14, 2, 'API Design',
 'Quality of REST/GraphQL API design: resource modelling, status codes, '
 'versioning, pagination, error handling, and idempotency.',
 10.0, 1.0,
 '{"criteria_text": "0-3: No RESTful awareness. 4-5: Basic CRUD understanding. 6-7: Good resource modelling with proper status codes. 8-9: Production-grade API design with pagination, filtering, versioning. 10: Expert design with HATEOAS, idempotency keys, rate limiting.", "applies_to": "technical"}',
 4),

(15, 2, 'Database Knowledge',
 'Understanding of relational and non-relational databases: schema design, '
 'indexing, query optimisation, normalisation, and data modelling.',
 10.0, 1.2,
 '{"criteria_text": "0-3: Cannot write basic SQL. 4-5: Basic CRUD queries. 6-7: Understands indexing and normalisation. 8-9: Can optimise queries, design schemas for scale. 10: Deep knowledge of query planners, partitioning, replication.", "applies_to": "technical"}',
 5),

-- Coding (backend-tuned)
(16, 2, 'Correctness',
 'Whether the solution produces correct output and handles edge cases. '
 'For backend roles, includes error handling and input validation.',
 10.0, 1.5,
 '{"criteria_text": "0-3: Does not compile/run. 4-5: Works for happy path only. 6-7: Handles most cases with basic error handling. 8-9: Robust solution with input validation and edge cases. 10: Production-ready with proper error propagation.", "applies_to": "coding"}',
 6),

(17, 2, 'Code Quality',
 'Readability, proper error handling patterns, separation of concerns, '
 'and adherence to backend best practices (dependency injection, etc.).',
 10.0, 1.0,
 '{"criteria_text": "0-3: Unreadable or monolithic. 4-5: Works but poorly structured. 6-7: Reasonable structure with some separation. 8-9: Clean architecture with proper patterns. 10: Production-grade with DI, proper logging, and testability.", "applies_to": "coding"}',
 7)

ON CONFLICT (id) DO NOTHING;

-- Reset sequence past the last explicit ID
SELECT setval('public.rubric_dimensions_id_seq', GREATEST(
  (SELECT COALESCE(MAX(id), 0) FROM public.rubric_dimensions), 17
));


-- ============================================================================
-- PART 4: Map rubrics to interview templates
-- ============================================================================
-- Existing templates (from DEV-16):
--   1 = DSA Fundamentals
--   2 = System Design
--   3 = Backend Engineering
--   4 = Frontend Development
--   5 = Behavioral Interview
--   6 = DevOps Assessment
--
-- Mapping strategy:
--   - Templates 1, 4, 5, 6 use the General rubric (id=1)
--   - Template 3 (Backend Engineering) uses the Backend rubric (id=2)
--   - Template 2 (System Design) uses the Backend rubric (id=2) because
--     it shares system-thinking and trade-off dimensions
--

INSERT INTO public.interview_template_rubrics
    (id, interview_template_id, rubric_id, section_name)
VALUES
    -- General Technical rubric mapped to DSA, Frontend, Behavioral, DevOps
    (1, 1, 1, NULL),   -- DSA Fundamentals → General
    (2, 4, 1, NULL),   -- Frontend Development → General
    (3, 5, 1, NULL),   -- Behavioral Interview → General
    (4, 6, 1, NULL),   -- DevOps Assessment → General

    -- Backend Engineer rubric mapped to Backend and System Design templates
    (5, 3, 2, NULL),   -- Backend Engineering → Backend Engineer
    (6, 2, 2, NULL)    -- System Design → Backend Engineer
ON CONFLICT (id) DO NOTHING;

-- Reset sequence past the last explicit ID
SELECT setval('public.interview_template_rubrics_id_seq', GREATEST(
  (SELECT COALESCE(MAX(id), 0) FROM public.interview_template_rubrics), 6
));
