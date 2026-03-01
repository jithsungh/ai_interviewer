// === UNIFIED AI INTERVIEWER ERD ===
// Combines admin-focused features (erd2) with evaluation-focused features (erd1)
//
// === ARCHITECTURE INVARIANTS (MUST ENFORCE) ===
//
// 1. EXCHANGE IMMUTABILITY
//    After creation, interview_exchanges cannot modify:
//    - question_text, expected_answer, difficulty_at_time (question snapshot)
//    - response_text, response_code, response_time_ms (candidate response)
//    Only evaluations may be appended/versioned
//
// 2. ONE EXCHANGE = ONE EVALUATION
//    evaluations.interview_exchange_id is UNIQUE
//    No multiple "final" scores per exchange
//
// 3. TEMPLATE IMMUTABILITY AFTER USE
//    Once interview_submissions references a template:
//    - DO NOT edit template_structure
//    - Create new template version instead
//
// 4. RUNTIME NEVER JOINS CONFIG DYNAMICALLY
//    At submission creation:
//    - role → template resolved ONCE
//    - stored in interview_submissions.template_id
//    - never recalculated during runtime
//
// 5. SINGLE SOURCE OF TRUTH
//    - Role targeting: use interview_template_roles (NOT role_category text)
//    - Vector embeddings: use embeddings.source_type/source_id (NOT embedding_id FK)
//    - Window-role-template: direct mapping (NO intermediate window_roles table)

// === ENUMS ===
// user_status: active, inactive, banned
// organization_type: company, non_profit, educational
// organization_plan: free, pro, enterprise
// organization_status: active, inactive, suspended
// admin_role: superadmin, admin, read_only
// admin_status: active, inactive, suspended
// candidate_plan: free, pro, prime
// template_scope: public, organization, private
// interview_scope: global, local, only_invited
// interview_mode: async, live, hybrid
// submission_status: pending, in_progress, completed, reviewed
// difficulty_level: easy, medium, hard
// question_type: behavioral, technical, situational, coding
// coding_topic_type: data_structure, algorithm, pattern, system_design, language_specific, traversal
// code_execution_status: pending, running, passed, failed, error, timeout, memory_exceeded
// problem_pipeline_status: pending, solution_fetched, tests_validated, templates_validated, imported
// problem_source: leetcode
// proctoring_severity: low, medium, high, critical
// report_type: candidate_summary, technical_breakdown, behavioral_analysis, proctoring_risk
// evaluator_type: ai, human, hybrid
// media_type: video, audio, screen_recording

// =============================================
// === CORE ENTITIES ===
// =============================================

users [icon: user, color: blue] {
  id bigserial pk
  name text
  email text unique
  password_hash text
  status user_status
  created_at timestamptz
  updated_at timestamptz
  user_type varchar(20) // admin or candidate
  last_login_at timestamptz
  token_version int // forced logout via increment
}

organizations [icon: building, color: purple] {
  id bigserial pk
  name text
  organization_type organization_type
  plan organization_plan
  domain text
  status organization_status
  policy_config jsonb // from erd1: tenant policy configuration
  metadata jsonb
  created_at timestamptz
  updated_at timestamptz
}

candidates [icon: user-check, color: green] {
  id bigserial pk
  user_id bigint
  plan candidate_plan
  status user_status
  profile_metadata jsonb
  created_at timestamptz
  updated_at timestamptz
}

admins [icon: shield, color: orange] {
  id bigserial pk
  user_id bigint
  organization_id bigint
  role admin_role
  status admin_status
  created_at timestamptz
  updated_at timestamptz
}

// =============================================
// === ROLES & TOPICS ===
// =============================================

roles [icon: briefcase, color: yellow] {
  id bigserial pk
  name text
  description text
  scope template_scope
  organization_id bigint
  created_at timestamptz
  updated_at timestamptz
}

// General topics for behavioral/technical questions
topics [icon: tag, color: cyan] {
  id bigserial pk
  name text
  description text
  parent_topic_id bigint
  scope template_scope
  organization_id bigint
  estimated_time_minutes int
  created_at timestamptz
  updated_at timestamptz
}

// Specialized topics for coding problems
coding_topics [icon: code, color: cyan] {
  id bigserial pk
  name text
  description text
  topic_type coding_topic_type // data_structure, algorithm, pattern, etc.
  parent_topic_id bigint
  scope template_scope
  organization_id bigint
  created_at timestamptz
  updated_at timestamptz
  display_order int
}

role_topics [icon: link, color: gray] {
  role_id bigint pk
  topic_id bigint pk
}

role_coding_topics [icon: link, color: gray] {
  role_id bigint pk
  coding_topic_id bigint pk
}

// =============================================
// === INTERVIEW TEMPLATES ===
// =============================================

interview_templates [icon: file-text, color: teal] {
  id bigserial pk
  name text
  description text
  scope template_scope
  organization_id bigint
  template_structure jsonb
  rules jsonb // interview rules/constraints
  total_estimated_time_minutes int
  version int
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

interview_template_roles [icon: link, color: gray] {
  interview_template_id bigint pk
  role_id bigint pk
}

// Links templates to rubrics for evaluation
interview_template_rubrics [icon: link, color: gray] {
  id bigserial pk
  interview_template_id bigint
  rubric_id bigint
  section_name text // which section of template uses this rubric
  created_at timestamptz
}

// =============================================
// === SUBMISSION WINDOWS ===
// =============================================

interview_submission_windows [icon: calendar, color: indigo] {
  id bigserial pk
  organization_id bigint
  admin_id bigint
  name text
  scope interview_scope
  start_time timestamptz
  end_time timestamptz
  timezone text
  max_allowed_submissions int
  allow_after_end_time boolean
  allow_resubmission boolean
  created_at timestamptz
  updated_at timestamptz
}

// Direct window-role-template mapping (simplified)
window_role_templates [icon: link, color: gray] {
  id bigserial pk
  window_id bigint
  role_id bigint
  template_id bigint
  selection_weight int
  created_at timestamptz
}

// =============================================
// === QUESTIONS ===
// =============================================
// Questions selected dynamically via template_structure
// using topic filters, difficulty, and question_type

questions [icon: help-circle, color: pink] {
  id bigserial pk
  question_text text
  answer_text text
  question_type question_type // behavioral, technical, situational, coding
  difficulty difficulty_level
  scope template_scope
  organization_id bigint
  source_type text // manual, generated, imported
  estimated_time_minutes int
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

question_topics [icon: link, color: gray] {
  question_id bigint pk
  topic_id bigint pk
}

// =============================================
// === CODING PROBLEMS ===
// =============================================

coding_problems [icon: code, color: red] {
  id bigserial pk
  body text
  difficulty difficulty_level
  scope template_scope
  organization_id bigint
  constraints text
  estimated_time_minutes int
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
  source_name problem_source
  source_id text
  source_slug text
  title text
  description text
  raw_content jsonb
  content_overridden boolean
  overridden_content text
  examples jsonb
  constraints_structured jsonb
  hints jsonb
  stats jsonb
  code_snippets jsonb
  likes int
  dislikes int
  acceptance_rate numeric
  pipeline_status problem_pipeline_status
}

coding_test_cases [icon: check-square, color: red] {
  id bigserial pk
  coding_problem_id bigint
  input_data text
  expected_output text
  is_hidden boolean
  weight numeric // scoring weight for this test case
  created_at timestamptz
}

coding_problem_topics [icon: link, color: gray] {
  coding_problem_id bigint pk
  coding_topic_id bigint pk
}

// =============================================
// === PROGRAMMING LANGUAGES & TEMPLATES ===
// =============================================

programming_languages [icon: code, color: blue] {
  id bigserial pk
  name text
  slug text
  version text
  execution_environment text
  is_active boolean
  display_order int
  created_at timestamptz
  updated_at timestamptz
}

problem_language_templates [icon: file-code, color: blue] {
  id bigserial pk
  problem_id bigint
  language_id bigint
  template_code text
  entry_function text
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
  solution_code text
}

source_topics [icon: tag, color: cyan] {
  id bigserial pk
  name text
  created_at timestamptz
  updated_at timestamptz
  coding_topic_id bigint
}

// =============================================
// === RUBRICS & EVALUATION CRITERIA ===
// =============================================

rubrics [icon: list, color: orange] {
  id bigserial pk
  organization_id bigint
  name text
  description text
  scope template_scope
  schema jsonb // detailed rubric structure
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

rubric_dimensions [icon: sliders, color: orange] {
  id bigserial pk
  rubric_id bigint
  dimension_name text
  description text
  max_score numeric
  weight numeric
  criteria jsonb // scoring criteria for each level
  sequence_order int
  created_at timestamptz
}

// =============================================
// === INTERVIEW SUBMISSIONS ===
// =============================================

interview_submissions [icon: send, color: green] {
  id bigserial pk
  candidate_id bigint
  window_id bigint
  role_id bigint
  template_id bigint
  mode interview_mode
  status submission_status
  final_score numeric
  consent_captured boolean
  scheduled_start timestamptz
  scheduled_end timestamptz
  started_at timestamptz
  submitted_at timestamptz
  created_at timestamptz
  updated_at timestamptz
}

// =============================================
// === INTERVIEW EXCHANGES (Core Runtime Unit) ===
// =============================================
// One exchange = one question + response + evaluation
// This is the immutable unit of an interview interaction

interview_exchanges [icon: message-square, color: green] {
  id bigserial pk
  interview_submission_id bigint
  sequence_order int
  question_id bigint // reference if reused from question bank
  coding_problem_id bigint // reference if coding question
  question_text text // immutable snapshot
  expected_answer text
  difficulty_at_time difficulty_level
  response_text text // candidate's text response
  response_code text // candidate's code (if coding)
  response_time_ms int
  ai_followup_message text // AI follow-up or clarification
  content_metadata jsonb // pauses, latency, tokens
  created_at timestamptz
}

// =============================================
// === MEDIA ARTIFACTS (Session Recordings) ===
// =============================================
// Stores video/audio/screen recordings of specific exchanges

media_artifacts [icon: video, color: red] {
  id bigserial pk
  interview_exchange_id bigint
  media_type media_type
  storage_uri text
  duration_seconds int
  file_size_bytes bigint
  captured_at timestamptz
  retention_expiry timestamptz
  created_at timestamptz
}

// =============================================
// === AUDIO ANALYTICS (Speech Analysis) ===
// =============================================
// Analyzes audio from a specific exchange

audio_analytics [icon: mic, color: green] {
  id bigserial pk
  interview_exchange_id bigint // unique - one analysis per exchange
  transcript text
  confidence_score numeric
  speech_rate_wpm int
  filler_word_count int
  sentiment_score numeric
  analysis_metadata jsonb
  created_at timestamptz
}

// =============================================
// === EVALUATIONS (Exchange-Level Scoring) ===
// =============================================
// Evaluates candidate's response in a specific exchange

evaluations [icon: percent, color: orange] {
  id bigserial pk
  interview_exchange_id bigint // unique - one evaluation per exchange
  rubric_id bigint
  model_id bigint
  evaluator_type evaluator_type
  total_score numeric
  explanation jsonb
  is_final boolean
  evaluated_at timestamptz
  created_at timestamptz
}

evaluation_dimension_scores [icon: bar-chart, color: orange] {
  id bigserial pk
  evaluation_id bigint
  rubric_dimension_id bigint
  score numeric
  justification text
  created_at timestamptz
}

// =============================================
// === CODE SUBMISSIONS ===
// =============================================

code_submissions [icon: terminal, color: red] {
  id bigserial pk
  interview_exchange_id bigint
  coding_problem_id bigint
  language text
  source_code text
  execution_status code_execution_status
  score numeric
  execution_time_ms int
  memory_kb int
  submitted_at timestamptz
  created_at timestamptz
  executed_at timestamptz
}

code_execution_results [icon: activity, color: red] {
  id bigserial pk
  code_submission_id bigint
  test_case_id bigint
  passed boolean
  actual_output text
  runtime_ms int
  memory_kb int
  compiler_output text
  runtime_output text
  feedback text
  created_at timestamptz
  exit_code int
}

// =============================================
// === PROCTORING EVENTS ===
// =============================================

proctoring_events [icon: eye, color: orange] {
  id bigserial pk
  interview_submission_id bigint
  event_type text
  severity proctoring_severity
  risk_weight numeric
  evidence jsonb
  occurred_at timestamptz
  created_at timestamptz
}

// =============================================
// === INTERVIEW RESULTS (Frozen Scoring Snapshot) ===
// =============================================
// Stores computed final results with full context snapshot
// ONE result per submission (unless re-evaluated with version)

interview_results [icon: clipboard-check, color: blue] {
  id bigserial pk
  interview_submission_id bigint // unique per version
  
  // Final computed outputs
  final_score numeric
  normalized_score numeric // percentage 0-100
  result_status text // pass, fail, borderline, incomplete
  recommendation text // hire, no_hire, review, strong_hire
  
  // Scoring context snapshots (immutable)
  scoring_version text // v1.0, v2-review, etc.
  rubric_snapshot jsonb // rubric ids + dimension weights used
  template_weight_snapshot jsonb // section weights from template at time
  
  // Section-wise breakdown (for UI/drill-down)
  section_scores jsonb // {resume: 8.5, coding: 32.0, ...}
  
  // Qualitative assessment
  strengths text
  weaknesses text
  summary_notes text
  
  // Metadata
  generated_by text // system, reviewer_id, model_name
  model_id bigint
  is_current boolean // latest version flag
  computed_at timestamptz
  created_at timestamptz
}

// =============================================
// === SUPPLEMENTARY REPORTS ===
// =============================================
// Optional detailed reports (technical breakdown, proctoring risk, etc.)
// Separate from core interview_results

supplementary_reports [icon: file-text, color: blue] {
  id bigserial pk
  interview_submission_id bigint
  report_type report_type // technical_breakdown, behavioral_analysis, proctoring_risk
  content jsonb // flexible report structure
  generated_by text
  model_id bigint
  created_at timestamptz
}

// =============================================
// === RESUMES & JOB DESCRIPTIONS ===
// =============================================

resumes [icon: file, color: blue] {
  id bigserial pk
  candidate_id bigint
  file_url text
  parsed_text text
  extracted_data jsonb
  uploaded_at timestamptz
  created_at timestamptz
}

job_descriptions [icon: clipboard, color: purple] {
  id bigserial pk
  organization_id bigint
  role_id bigint
  title text
  description_text text
  requirements jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

// =============================================
// === AI MODELS & EMBEDDINGS ===
// =============================================

models [icon: cpu, color: purple] {
  id bigserial pk
  provider text
  name text
  model_type text // llm, embedding, speech-to-text, etc.
  version text
  config jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

embeddings [icon: database, color: purple] {
  id bigserial pk
  organization_id bigint
  source_type text // resume, job_description, question, etc.
  source_id bigint
  model_id bigint
  vector_ref text // reference to vector store
  dimensions int
  created_at timestamptz
}

// =============================================
// === PROMPT TEMPLATES ===
// =============================================

prompt_templates [icon: zap, color: yellow] {
  id bigserial pk
  name text
  prompt_type text // question_generation, evaluation, follow_up, etc.
  scope template_scope
  organization_id bigint
  system_prompt text
  user_prompt text
  model_id bigint
  model_config jsonb
  version int
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

// =============================================
// === AUDITING ===
// =============================================

audit_logs [icon: lock, color: gray] {
  id bigserial pk
  organization_id bigint
  actor_user_id bigint
  action text
  entity_type text
  entity_id bigint
  old_value jsonb
  new_value jsonb
  ip_address inet
  user_agent text
  created_at timestamptz
}

// =============================================
// === AUTH AUDIT LOG & REFRESH TOKENS ===
// =============================================

auth_audit_log [icon: lock, color: gray] {
  id bigserial pk
  user_id bigint
  event_type varchar(50) // login_success, login_failure, logout, token_refresh, password_change, etc.
  ip_address inet
  user_agent text
  metadata jsonb // {error_code, email, organization_id, admin_role, etc.}
  created_at timestamptz
}

refresh_tokens [icon: key, color: gray] {
  id bigserial pk
  user_id bigint
  token_hash text unique // SHA-256 hash, original never stored
  device_info text
  ip_address inet
  issued_at timestamptz
  expires_at timestamptz
  revoked_at timestamptz
  revoked_reason varchar(100) // logout, password_change, admin_action, suspicious, rotation
  created_at timestamptz
}

// =============================================
// === TENANT OVERRIDE TABLES ===
// =============================================
// Tenant-specific overrides for super-org content.
// Each follows the same pattern: org + base_content_id + override_fields jsonb.

coding_problem_overrides [icon: layers, color: gray] {
  id bigserial pk
  organization_id bigint
  base_content_id bigint // -> coding_problems.id
  override_fields jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

question_overrides [icon: layers, color: gray] {
  id bigserial pk
  organization_id bigint
  base_content_id bigint // -> questions.id
  override_fields jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

role_overrides [icon: layers, color: gray] {
  id bigserial pk
  organization_id bigint
  base_content_id bigint // -> roles.id
  override_fields jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

rubric_overrides [icon: layers, color: gray] {
  id bigserial pk
  organization_id bigint
  base_content_id bigint // -> rubrics.id
  override_fields jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

template_overrides [icon: layers, color: gray] {
  id bigserial pk
  organization_id bigint
  base_content_id bigint // -> interview_templates.id
  override_fields jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

topic_overrides [icon: layers, color: gray] {
  id bigserial pk
  organization_id bigint
  base_content_id bigint // -> topics.id
  override_fields jsonb
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
}

// =============================================
// === RELATIONSHIPS ===
// =============================================

// --- Core User Relationships ---
candidates.user_id > users.id
admins.user_id > users.id
admins.organization_id > organizations.id

// --- Roles & Topics ---
roles.organization_id > organizations.id
topics.parent_topic_id > topics.id
topics.organization_id > organizations.id
coding_topics.parent_topic_id > coding_topics.id
coding_topics.organization_id > organizations.id
role_topics.role_id > roles.id
role_topics.topic_id > topics.id
role_coding_topics.role_id > roles.id
role_coding_topics.coding_topic_id > coding_topics.id

// --- Templates ---
interview_templates.organization_id > organizations.id
interview_template_roles.interview_template_id > interview_templates.id
interview_template_roles.role_id > roles.id
interview_template_rubrics.interview_template_id > interview_templates.id
interview_template_rubrics.rubric_id > rubrics.id

// --- Submission Windows ---
interview_submission_windows.organization_id > organizations.id
interview_submission_windows.admin_id > admins.id
window_role_templates.window_id > interview_submission_windows.id
window_role_templates.role_id > roles.id
window_role_templates.template_id > interview_templates.id

// --- Questions ---
questions.organization_id > organizations.id
question_topics.question_id > questions.id
question_topics.topic_id > topics.id

// --- Coding Problems ---
coding_problems.organization_id > organizations.id
coding_test_cases.coding_problem_id > coding_problems.id
coding_problem_topics.coding_problem_id > coding_problems.id
coding_problem_topics.coding_topic_id > coding_topics.id

// --- Programming Languages & Templates ---
problem_language_templates.problem_id > coding_problems.id
problem_language_templates.language_id > programming_languages.id
source_topics.coding_topic_id > coding_topics.id

// --- Rubrics ---
rubrics.organization_id > organizations.id
rubric_dimensions.rubric_id > rubrics.id

// --- Interview Submissions ---
interview_submissions.candidate_id > candidates.id
interview_submissions.window_id > interview_submission_windows.id
interview_submissions.role_id > roles.id
interview_submissions.template_id > interview_templates.id

// --- Interview Exchanges (Core Runtime) ---
interview_exchanges.interview_submission_id > interview_submissions.id
interview_exchanges.question_id > questions.id
interview_exchanges.coding_problem_id > coding_problems.id

// --- Media Artifacts (Exchange-scoped) ---
media_artifacts.interview_exchange_id > interview_exchanges.id

// --- Audio Analytics (Exchange-scoped) ---
audio_analytics.interview_exchange_id > interview_exchanges.id

// --- Evaluations (Exchange-scoped) ---
evaluations.interview_exchange_id > interview_exchanges.id
evaluations.rubric_id > rubrics.id
evaluations.model_id > models.id
evaluation_dimension_scores.evaluation_id > evaluations.id
evaluation_dimension_scores.rubric_dimension_id > rubric_dimensions.id

// --- Code Submissions (Exchange-scoped) ---
code_submissions.interview_exchange_id > interview_exchanges.id
code_submissions.coding_problem_id > coding_problems.id
code_execution_results.code_submission_id > code_submissions.id
code_execution_results.test_case_id > coding_test_cases.id

// --- Proctoring ---
proctoring_events.interview_submission_id > interview_submissions.id

// --- Interview Results (Frozen Scores) ---
interview_results.interview_submission_id > interview_submissions.id
interview_results.model_id > models.id

// --- Supplementary Reports ---
supplementary_reports.interview_submission_id > interview_submissions.id
supplementary_reports.model_id > models.id

// --- Resumes & Jobs ---
resumes.candidate_id > candidates.id
job_descriptions.organization_id > organizations.id
job_descriptions.role_id > roles.id

// --- AI Models & Embeddings ---
embeddings.organization_id > organizations.id
embeddings.model_id > models.id

// --- Prompt Templates ---
prompt_templates.organization_id > organizations.id
prompt_templates.model_id > models.id

// --- Auditing ---
audit_logs.organization_id > organizations.id
audit_logs.actor_user_id > users.id

// --- Auth Audit Log & Refresh Tokens ---
auth_audit_log.user_id > users.id
refresh_tokens.user_id > users.id

// --- Tenant Override Tables ---
coding_problem_overrides.organization_id > organizations.id
coding_problem_overrides.base_content_id > coding_problems.id
question_overrides.organization_id > organizations.id
question_overrides.base_content_id > questions.id
role_overrides.organization_id > organizations.id
role_overrides.base_content_id > roles.id
rubric_overrides.organization_id > organizations.id
rubric_overrides.base_content_id > rubrics.id
template_overrides.organization_id > organizations.id
template_overrides.base_content_id > interview_templates.id
topic_overrides.organization_id > organizations.id
topic_overrides.base_content_id > topics.id
