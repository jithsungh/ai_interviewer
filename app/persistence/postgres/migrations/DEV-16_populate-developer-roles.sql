--
-- Migration DEV-16: Populate Developer Roles
--
-- Purpose: Seed the roles table with standard developer role types
--          to be used in interview template configuration and
--          candidate skill matching.
-- Date: 2026-03-05
-- Module: app/question
-- Ticket: DEV-16
--
-- Changes:
--   1. Insert 7 standard developer roles into roles table
--
-- Invariants preserved:
--   - All roles have scope='organization' (org-specific)
--   - All roles belong to organization_id=1 (super organization)
--   - IDs are explicit (1-7) for deterministic references
--   - No SRS invariant broken (populating existing table)
--   - No ERD invariant violated (valid FK relationships)
--   - No duplicate role names (unique constraint respected)
--
-- Rollback: See DEV-16_populate-developer-roles_rollback.sql
--

-- ============================================================================
-- PART 1: Populate roles table with standard developer roles
-- ============================================================================

INSERT INTO public.roles (id, name, description, scope, organization_id)
VALUES
    (1, 'Backend Developer',
     'Develops server-side applications, APIs, databases, and business logic',
     'organization', 1),
    
    (2, 'Frontend Developer',
     'Builds client-side interfaces, user experiences, and frontend architecture',
     'organization', 1),
    
    (3, 'Full Stack Developer',
     'Works across both frontend and backend, handling end-to-end development',
     'organization', 1),
    
    (4, 'DevOps Engineer',
     'Manages infrastructure, CI/CD pipelines, deployment automation, and system reliability',
     'organization', 1),
    
    (5, 'Data Engineer',
     'Designs and maintains data pipelines, warehouses, and data processing systems',
     'organization', 1),
    
    (6, 'Mobile App Developer',
     'Creates native or cross-platform mobile applications for iOS and Android',
     'organization', 1),
    
    (7, 'ML Engineer',
     'Develops machine learning models, pipelines, and AI-powered applications',
     'organization', 1)

ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- PART 2: Update sequence to continue from ID 8
-- ============================================================================

-- Ensure the sequence starts from 8 for future role insertions
SELECT setval('public.roles_id_seq', 7, true);

