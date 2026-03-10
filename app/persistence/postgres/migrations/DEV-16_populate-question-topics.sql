--
-- Migration DEV-16: Populate Question-Topics Mapping & Behavioral Questions
--
-- Purpose: Create the missing link between questions and topics in the
--          question_topics junction table, and add behavioral questions
--          for the behavioral interview section.
-- Date: 2026-03-10
-- Module: app/question
-- Ticket: DEV-16 (continuation)
--
-- Changes:
--   1. Populate question_topics mapping (515 questions × 1 topic each)
--   2. Insert 15 behavioral questions (IDs 516-530)
--
-- Dependencies: 
--   - DEV-16_populate-topics-and-role-topics.sql (topics 1-103)
--   - DEV-16_populate-questions.sql (questions 1-515)
--
-- Mapping formula: 
--   Questions 1-5   → Topic 1 (Computer Networks)
--   Questions 6-10  → Topic 2 (Operating Systems)
--   Questions 11-15 → Topic 3 (Object-Oriented Programming)
--   ... pattern continues: Questions ((N-1)*5+1) to (N*5) → Topic N
--

-- ============================================================================
-- CLEANUP: Remove existing mappings (idempotent)
-- ============================================================================
DELETE FROM public.question_topics WHERE question_id BETWEEN 1 AND 530;

-- ============================================================================
-- PART 1: Populate question_topics mappings for technical questions
-- Each topic (1-103) has 5 questions assigned to it
-- ============================================================================

-- Generate mappings using a CTE for all topics 1-103
INSERT INTO public.question_topics (question_id, topic_id)
SELECT 
    q.id as question_id,
    ((q.id - 1) / 5) + 1 as topic_id
FROM public.questions q
WHERE q.id BETWEEN 1 AND 515
  AND ((q.id - 1) / 5) + 1 <= 103;

-- ============================================================================
-- PART 2: Insert behavioral questions (IDs 516-530)
-- These are soft-skill and interpersonal questions for behavioral sections
-- ============================================================================

INSERT INTO public.questions (id, question_text, answer_text, question_type, difficulty, scope, organization_id, source_type, estimated_time_minutes, is_active)
VALUES
    -- Behavioral: Teamwork & Collaboration
    (516, 'Tell me about a time when you had to work with a difficult team member. How did you handle the situation?',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    (517, 'Describe a situation where you had to collaborate with team members from different departments or backgrounds.',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    (518, 'Give an example of a time when you had to give constructive feedback to a colleague.',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    -- Behavioral: Problem Solving & Decision Making
    (519, 'Describe a complex technical problem you solved. What was your approach?',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    (520, 'Tell me about a time when you had to make a difficult decision with limited information.',
     NULL, 'behavioral', 'hard', 'organization', 1, 'custom', 7, true),
    
    (521, 'Give an example of when you identified a problem before it became critical and how you addressed it.',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    -- Behavioral: Leadership & Initiative
    (522, 'Describe a time when you took initiative on a project without being asked.',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    (523, 'Tell me about a time when you had to lead a project or team. What challenges did you face?',
     NULL, 'behavioral', 'hard', 'organization', 1, 'custom', 7, true),
    
    (524, 'Give an example of how you mentored or helped a junior team member grow.',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    -- Behavioral: Adaptability & Learning
    (525, 'Describe a situation where you had to quickly learn a new technology or skill to complete a project.',
     NULL, 'behavioral', 'easy', 'organization', 1, 'custom', 3, true),
    
    (526, 'Tell me about a time when project requirements changed significantly. How did you adapt?',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    (527, 'Give an example of receiving criticism or negative feedback. How did you respond?',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true),
    
    -- Behavioral: Conflict Resolution & Communication
    (528, 'Describe a disagreement you had with a manager or senior team member. How was it resolved?',
     NULL, 'behavioral', 'hard', 'organization', 1, 'custom', 7, true),
    
    (529, 'Tell me about a time when you had to explain a complex technical concept to a non-technical stakeholder.',
     NULL, 'behavioral', 'easy', 'organization', 1, 'custom', 3, true),
    
    (530, 'Give an example of a time when you had to manage competing priorities or deadlines.',
     NULL, 'behavioral', 'medium', 'organization', 1, 'custom', 5, true);

-- ============================================================================
-- Verification queries (optional - run manually to verify)
-- ============================================================================
-- Check question_topics count:
-- SELECT COUNT(*) FROM question_topics; -- Should be 515

-- Check behavioral questions:
-- SELECT COUNT(*) FROM questions WHERE question_type = 'behavioral'; -- Should be 15

-- Check if template 3 can now get questions:
-- SELECT COUNT(*) FROM questions q 
-- JOIN question_topics qt ON q.id = qt.question_id 
-- WHERE qt.topic_id IN (7, 94, 18, 17, 20) AND q.is_active = true;
