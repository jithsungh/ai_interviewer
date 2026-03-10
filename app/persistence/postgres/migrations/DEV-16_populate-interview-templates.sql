--
-- Migration DEV-16: Populate Interview Templates
--
-- Purpose: Seed the interview_templates table with standard interview
--          templates matching frontend template definitions, and map
--          them to appropriate roles via interview_template_roles.
-- Date: 2026-03-09
-- Module: app/interview
-- Ticket: DEV-16
--
-- Changes:
--   1. Insert 6 interview templates (DSA, System Design, Backend, Frontend,
--      Behavioral, DevOps) into interview_templates table
--   2. Map templates to roles in interview_template_roles junction table
--
-- Invariants preserved:
--   - All templates have scope='organization' (org-specific)
--   - All templates belong to organization_id=1 (super organization)
--   - template_structure follows graduate_interview_template.json schema
--   - Topic IDs reference existing topics from DEV-16_populate-topics
--   - Role IDs reference existing roles from DEV-16_populate-developer-roles
--   - No SRS invariant broken (populating existing tables)
--   - No ERD invariant violated (valid FK relationships)
--
-- Rollback: See DEV-16_populate-interview-templates_rollback.sql
--

-- ============================================================================
-- PART 1: Populate interview_templates table
-- ============================================================================

INSERT INTO public.interview_templates (id, name, description, scope, organization_id, template_structure, rules, total_estimated_time_minutes, version, is_active)
VALUES

-- --------------------------------------------------------------------------
-- Template 1: DSA Fundamentals
-- --------------------------------------------------------------------------
(1,
 'DSA Fundamentals',
 'Data Structures & Algorithms assessment covering arrays, trees, graphs, and dynamic programming',
 'organization', 1,
 '{
    "template_name": "DSA Fundamentals",
    "template_version": "1.0",
    "target_level": "mid_level",
    "estimated_duration_minutes": 60,
    "total_questions": 4,

    "sections": {
      "resume_analysis": {
        "enabled": false,
        "weight": 0
      },

      "self_introduction": {
        "enabled": false,
        "weight": 0
      },

      "topics_assessment": {
        "enabled": true,
        "total_questions": 2,
        "weight": 30,
        "topics": [
          {
            "topic_id": 6,
            "topic_name": "Data Structures and Algorithms",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium", "hard"],
            "weight": 60
          },
          {
            "topic_id": 3,
            "topic_name": "Object-Oriented Programming",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 40
          }
        ]
      },

      "coding_round": {
        "enabled": false,
        "question_count": 4,
        "max_duration_minutes": 45,
        "weight": 50,

        "problems": [
          {
            "difficulty": "easy",
            "topics": ["arrays", "strings"],
            "estimated_time_minutes": 8,
            "weight": 15
          },
          {
            "difficulty": "medium",
            "topics": ["trees", "hash_maps"],
            "estimated_time_minutes": 12,
            "weight": 30
          },
          {
            "difficulty": "medium",
            "topics": ["graphs", "dynamic_programming"],
            "estimated_time_minutes": 12,
            "weight": 30
          },
          {
            "difficulty": "hard",
            "topics": ["dynamic_programming", "graphs"],
            "estimated_time_minutes": 15,
            "weight": 25
          }
        ],

        "execution_config": {
          "languages_allowed": ["python3", "java", "cpp"],
          "time_limit_ms": 2000,
          "memory_limit_kb": 262144
        },

        "scoring": {
          "correctness_weight": 80,
          "code_quality_weight": 20,
          "minimum_pass_percentage": 50
        }
      },

      "complexity_analysis": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 5,
        "weight": 15,
        "expectations": ["time_complexity", "space_complexity"]
      },

      "behavioral": {
        "enabled": true,
        "weight": 0
      }
    },

    "scoring": {
      "strategy": "weighted_sum",
      "normalization": "percentage",
      "pass_threshold": 60,
      "section_weights": {
        "topics_assessment": 30,
        "coding_round": 50,
        "complexity_analysis": 15,
        "bonus_points": 5
      }
    },

    "proctoring": {
      "enabled": true,
      "advisory_only": true,
      "basic_monitoring": ["tab_switch", "face_detection"]
    },

    "settings": {
      "auto_submit_on_timeout": true,
      "allow_resume_session": false,
      "show_progress": true
    }
  }'::jsonb,
 NULL,
 60,
 1,
 true
),

-- --------------------------------------------------------------------------
-- Template 2: System Design
-- --------------------------------------------------------------------------
(2,
 'System Design',
 'Design scalable distributed systems with focus on architecture and trade-offs',
 'organization', 1,
 '{
    "template_name": "System Design",
    "template_version": "1.0",
    "target_level": "senior_level",
    "estimated_duration_minutes": 90,
    "total_questions": 2,

    "sections": {
      "resume_analysis": {
        "enabled": false,
        "weight": 0
      },

      "self_introduction": {
        "enabled": false,
        "weight": 0
      },

      "topics_assessment": {
        "enabled": true,
        "total_questions": 4,
        "weight": 50,
        "topics": [
          {
            "topic_id": 91,
            "topic_name": "System Design Fundamentals",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["medium", "hard"],
            "weight": 25
          },
          {
            "topic_id": 92,
            "topic_name": "Distributed Systems",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["medium", "hard"],
            "weight": 25
          },
          {
            "topic_id": 94,
            "topic_name": "Database Design",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["medium", "hard"],
            "weight": 20
          },
          {
            "topic_id": 95,
            "topic_name": "Caching Architecture",
            "difficulty_strategy": "fixed",
            "difficulty": "medium",
            "weight": 15
          },
          {
            "topic_id": 96,
            "topic_name": "Load Balancing",
            "difficulty_strategy": "fixed",
            "difficulty": "medium",
            "weight": 15
          }
        ]
      },

      "coding_round": {
        "enabled": false,
        "question_count": 2,
        "max_duration_minutes": 30,
        "weight": 25,

        "problems": [
          {
            "difficulty": "medium",
            "topics": ["hash_maps", "design_patterns"],
            "estimated_time_minutes": 15,
            "weight": 50
          },
          {
            "difficulty": "hard",
            "topics": ["distributed_systems", "concurrency"],
            "estimated_time_minutes": 15,
            "weight": 50
          }
        ],

        "execution_config": {
          "languages_allowed": ["python3", "java", "cpp", "go"],
          "time_limit_ms": 3000,
          "memory_limit_kb": 524288
        },

        "scoring": {
          "correctness_weight": 60,
          "code_quality_weight": 40,
          "minimum_pass_percentage": 40
        }
      },

      "complexity_analysis": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 5,
        "weight": 10,
        "expectations": ["time_complexity", "space_complexity", "scalability_analysis"]
      },

      "behavioral": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 10,
        "weight": 15,
        "topics": ["technical_leadership", "trade_off_analysis", "problem_solving"]
      }
    },

    "scoring": {
      "strategy": "weighted_sum",
      "normalization": "percentage",
      "pass_threshold": 55,
      "section_weights": {
        "topics_assessment": 50,
        "coding_round": 25,
        "complexity_analysis": 10,
        "behavioral": 15
      }
    },

    "proctoring": {
      "enabled": true,
      "advisory_only": true,
      "basic_monitoring": ["tab_switch", "face_detection"]
    },

    "settings": {
      "auto_submit_on_timeout": true,
      "allow_resume_session": false,
      "show_progress": true
    }
  }'::jsonb,
 NULL,
 90,
 1,
 true
),

-- --------------------------------------------------------------------------
-- Template 3: Backend Engineering
-- --------------------------------------------------------------------------
(3,
 'Backend Engineering',
 'Server-side development covering APIs, databases, and backend patterns',
 'organization', 1,
 '{
    "template_name": "Backend Engineering",
    "template_version": "1.0",
    "target_level": "mid_level",
    "estimated_duration_minutes": 75,
    "total_questions": 5,

    "sections": {
      "resume_analysis": {
        "enabled": false,
        "weight": 10,
        "description": "ATS scoring and job description matching",
        "ats_scoring": {
          "enabled": true,
          "parse_resume": true,
          "extract_sections": ["education", "skills", "experience", "projects"],
          "match_against_job_description": true,
          "scoring_dimensions": [
            {
              "dimension": "skills_match",
              "weight": 40,
              "criteria": "Backend languages, frameworks, databases match"
            },
            {
              "dimension": "education_qualification",
              "weight": 20,
              "criteria": "Degree, relevant coursework"
            },
            {
              "dimension": "experience_relevance",
              "weight": 25,
              "criteria": "Backend development experience, API design, system work"
            },
            {
              "dimension": "resume_quality",
              "weight": 15,
              "criteria": "Format, clarity, completeness"
            }
          ],
          "minimum_match_score": 50
        }
      },

      "self_introduction": {
        "enabled": false,
        "question_count": 1,
        "max_duration_seconds": 120,
        "weight": 5,
        "interaction_mode": "audio",
        "audio_analysis": {
          "enabled": true,
          "track_metrics": ["speech_rate", "filler_words", "confidence"]
        }
      },

      "topics_assessment": {
        "enabled": true,
        "total_questions": 5,
        "weight": 25,
        "topics": [
          {
            "topic_id": 7,
            "topic_name": "RESTful APIs",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium", "hard"],
            "weight": 25
          },
          {
            "topic_id": 94,
            "topic_name": "Database Design",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 20
          },
          {
            "topic_id": 18,
            "topic_name": "API Security",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 20
          },
          {
            "topic_id": 17,
            "topic_name": "Caching Strategies",
            "difficulty_strategy": "fixed",
            "difficulty": "medium",
            "weight": 15
          },
          {
            "topic_id": 20,
            "topic_name": "Backend Testing",
            "difficulty_strategy": "fixed",
            "difficulty": "easy",
            "weight": 20
          }
        ]
      },

      "coding_round": {
        "enabled": false,
        "question_count": 3,
        "max_duration_minutes": 35,
        "weight": 35,

        "problems": [
          {
            "difficulty": "easy",
            "topics": ["arrays", "strings"],
            "estimated_time_minutes": 8,
            "weight": 20
          },
          {
            "difficulty": "medium",
            "topics": ["hash_maps", "api_design"],
            "estimated_time_minutes": 12,
            "weight": 35
          },
          {
            "difficulty": "medium",
            "topics": ["database_queries", "sorting"],
            "estimated_time_minutes": 12,
            "weight": 30
          },
          {
            "difficulty": "hard",
            "topics": ["system_design", "concurrency"],
            "estimated_time_minutes": 15,
            "weight": 15
          }
        ],

        "execution_config": {
          "languages_allowed": ["python3", "java", "cpp", "go"],
          "time_limit_ms": 2000,
          "memory_limit_kb": 262144
        },

        "scoring": {
          "correctness_weight": 75,
          "code_quality_weight": 25,
          "minimum_pass_percentage": 50
        }
      },

      "complexity_analysis": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 4,
        "weight": 10,
        "expectations": ["time_complexity", "space_complexity"]
      },

      "behavioral": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 5,
        "weight": 10,
        "topics": ["teamwork", "debugging_approach", "problem_solving"]
      }
    },

    "scoring": {
      "strategy": "weighted_sum",
      "normalization": "percentage",
      "pass_threshold": 60,
      "section_weights": {
        "resume_analysis": 10,
        "self_introduction": 5,
        "topics_assessment": 25,
        "coding_round": 35,
        "complexity_analysis": 10,
        "behavioral": 10,
        "bonus_points": 5
      }
    },

    "proctoring": {
      "enabled": true,
      "advisory_only": true,
      "basic_monitoring": ["tab_switch", "face_detection"]
    },

    "settings": {
      "auto_submit_on_timeout": true,
      "allow_resume_session": false,
      "show_progress": true
    }
  }'::jsonb,
 NULL,
 75,
 1,
 true
),

-- --------------------------------------------------------------------------
-- Template 4: Frontend Development
-- --------------------------------------------------------------------------
(4,
 'Frontend Development',
 'Modern frontend development with React, state management, and performance',
 'organization', 1,
 '{
    "template_name": "Frontend Development",
    "template_version": "1.0",
    "target_level": "mid_level",
    "estimated_duration_minutes": 60,
    "total_questions": 4,

    "sections": {
      "resume_analysis": {
        "enabled": false,
        "weight": 10,
        "description": "ATS scoring and job description matching",
        "ats_scoring": {
          "enabled": true,
          "parse_resume": true,
          "extract_sections": ["education", "skills", "experience", "projects"],
          "match_against_job_description": true,
          "scoring_dimensions": [
            {
              "dimension": "skills_match",
              "weight": 45,
              "criteria": "Frontend frameworks, JavaScript/TypeScript, CSS match"
            },
            {
              "dimension": "education_qualification",
              "weight": 15,
              "criteria": "Degree, relevant coursework"
            },
            {
              "dimension": "experience_relevance",
              "weight": 25,
              "criteria": "Frontend projects, portfolio, UI/UX work"
            },
            {
              "dimension": "resume_quality",
              "weight": 15,
              "criteria": "Format, clarity, completeness"
            }
          ],
          "minimum_match_score": 50
        }
      },

      "self_introduction": {
        "enabled": false,
        "question_count": 1,
        "max_duration_seconds": 120,
        "weight": 5,
        "interaction_mode": "audio",
        "audio_analysis": {
          "enabled": true,
          "track_metrics": ["speech_rate", "filler_words", "confidence"]
        }
      },

      "topics_assessment": {
        "enabled": true,
        "total_questions": 5,
        "weight": 25,
        "topics": [
          {
            "topic_id": 23,
            "topic_name": "React",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium", "hard"],
            "weight": 25
          },
          {
            "topic_id": 27,
            "topic_name": "State Management",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 20
          },
          {
            "topic_id": 28,
            "topic_name": "Web Performance Optimization",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 20
          },
          {
            "topic_id": 34,
            "topic_name": "Web Accessibility",
            "difficulty_strategy": "fixed",
            "difficulty": "easy",
            "weight": 15
          },
          {
            "topic_id": 26,
            "topic_name": "HTML/CSS",
            "difficulty_strategy": "fixed",
            "difficulty": "easy",
            "weight": 20
          }
        ]
      },

      "coding_round": {
        "enabled": false,
        "question_count": 4,
        "max_duration_minutes": 35,
        "weight": 30,

        "problems": [
          {
            "difficulty": "easy",
            "topics": ["dom_manipulation", "css_layout"],
            "estimated_time_minutes": 8,
            "weight": 20
          },
          {
            "difficulty": "medium",
            "topics": ["react_components", "state_management"],
            "estimated_time_minutes": 12,
            "weight": 30
          },
          {
            "difficulty": "medium",
            "topics": ["async_javascript", "api_integration"],
            "estimated_time_minutes": 10,
            "weight": 25
          },
          {
            "difficulty": "hard",
            "topics": ["performance_optimization", "custom_hooks"],
            "estimated_time_minutes": 12,
            "weight": 25
          }
        ],

        "execution_config": {
          "languages_allowed": ["javascript", "typescript"],
          "time_limit_ms": 2000,
          "memory_limit_kb": 262144
        },

        "scoring": {
          "correctness_weight": 70,
          "code_quality_weight": 30,
          "minimum_pass_percentage": 50
        }
      },

      "complexity_analysis": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 4,
        "weight": 10,
        "expectations": ["time_complexity", "space_complexity"]
      },

      "behavioral": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 5,
        "weight": 10,
        "topics": ["collaboration", "design_thinking", "problem_solving"]
      }
    },

    "scoring": {
      "strategy": "weighted_sum",
      "normalization": "percentage",
      "pass_threshold": 60,
      "section_weights": {
        "resume_analysis": 10,
        "self_introduction": 5,
        "topics_assessment": 25,
        "coding_round": 30,
        "complexity_analysis": 10,
        "behavioral": 10,
        "bonus_points": 10
      }
    },

    "proctoring": {
      "enabled": true,
      "advisory_only": true,
      "basic_monitoring": ["tab_switch", "face_detection"]
    },

    "settings": {
      "auto_submit_on_timeout": true,
      "allow_resume_session": false,
      "show_progress": true
    }
  }'::jsonb,
 NULL,
 60,
 1,
 true
),

-- --------------------------------------------------------------------------
-- Template 5: Behavioral Interview
-- --------------------------------------------------------------------------
(5,
 'Behavioral Interview',
 'Assess leadership, communication, and problem-solving through behavioral questions',
 'organization', 1,
 '{
    "template_name": "Behavioral Interview",
    "template_version": "1.0",
    "target_level": "all_levels",
    "estimated_duration_minutes": 45,
    "total_questions": 6,

    "sections": {
      "resume_analysis": {
        "enabled": false,
        "weight": 10,
        "description": "ATS scoring and job description matching",
        "ats_scoring": {
          "enabled": true,
          "parse_resume": true,
          "extract_sections": ["education", "skills", "experience", "projects"],
          "match_against_job_description": true,
          "scoring_dimensions": [
            {
              "dimension": "skills_match",
              "weight": 30,
              "criteria": "Soft skills, leadership experience, communication"
            },
            {
              "dimension": "education_qualification",
              "weight": 20,
              "criteria": "Degree, relevant coursework"
            },
            {
              "dimension": "experience_relevance",
              "weight": 35,
              "criteria": "Team leadership, cross-functional work, project management"
            },
            {
              "dimension": "resume_quality",
              "weight": 15,
              "criteria": "Format, clarity, completeness"
            }
          ],
          "minimum_match_score": 40
        }
      },

      "self_introduction": {
        "enabled": false,
        "question_count": 1,
        "max_duration_seconds": 180,
        "weight": 15,
        "interaction_mode": "audio",
        "audio_analysis": {
          "enabled": true,
          "track_metrics": ["speech_rate", "filler_words", "confidence", "articulation"]
        }
      },

      "topics_assessment": {
        "enabled": true,
        "weight": 0
      },

      "coding_round": {
        "enabled": false,
        "weight": 0
      },

      "complexity_analysis": {
        "enabled": true,
        "weight": 0
      },

      "behavioral": {
        "enabled": true,
        "question_count": 6,
        "max_duration_minutes": 30,
        "weight": 65,
        "topics": [
          "leadership",
          "conflict_resolution",
          "teamwork",
          "problem_solving",
          "communication",
          "adaptability"
        ],
        "difficulty_distribution": {
          "easy": 2,
          "medium": 3,
          "hard": 1
        }
      }
    },

    "scoring": {
      "strategy": "weighted_sum",
      "normalization": "percentage",
      "pass_threshold": 55,
      "section_weights": {
        "resume_analysis": 10,
        "self_introduction": 15,
        "behavioral": 65,
        "bonus_points": 10
      }
    },

    "proctoring": {
      "enabled": true,
      "advisory_only": true,
      "basic_monitoring": ["tab_switch", "face_detection"]
    },

    "settings": {
      "auto_submit_on_timeout": true,
      "allow_resume_session": false,
      "show_progress": true
    }
  }'::jsonb,
 NULL,
 45,
 1,
 true
),

-- --------------------------------------------------------------------------
-- Template 6: DevOps & Cloud
-- --------------------------------------------------------------------------
(6,
 'DevOps & Cloud',
 'Cloud infrastructure, CI/CD, containerization, and DevOps practices',
 'organization', 1,
 '{
    "template_name": "DevOps & Cloud",
    "template_version": "1.0",
    "target_level": "mid_level",
    "estimated_duration_minutes": 60,
    "total_questions": 4,

    "sections": {
      "resume_analysis": {
        "enabled": false,
        "weight": 10,
        "description": "ATS scoring and job description matching",
        "ats_scoring": {
          "enabled": true,
          "parse_resume": true,
          "extract_sections": ["education", "skills", "experience", "projects", "certifications"],
          "match_against_job_description": true,
          "scoring_dimensions": [
            {
              "dimension": "skills_match",
              "weight": 40,
              "criteria": "Cloud platforms, containerization, IaC tools, CI/CD"
            },
            {
              "dimension": "education_qualification",
              "weight": 15,
              "criteria": "Degree, certifications (AWS/Azure/GCP)"
            },
            {
              "dimension": "experience_relevance",
              "weight": 30,
              "criteria": "DevOps roles, infrastructure management, SRE experience"
            },
            {
              "dimension": "resume_quality",
              "weight": 15,
              "criteria": "Format, clarity, completeness"
            }
          ],
          "minimum_match_score": 50
        }
      },

      "self_introduction": {
        "enabled": false,
        "question_count": 1,
        "max_duration_seconds": 120,
        "weight": 5,
        "interaction_mode": "audio",
        "audio_analysis": {
          "enabled": true,
          "track_metrics": ["speech_rate", "filler_words", "confidence"]
        }
      },

      "topics_assessment": {
        "enabled": true,
        "total_questions": 5,
        "weight": 30,
        "topics": [
          {
            "topic_id": 37,
            "topic_name": "Docker",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium", "hard"],
            "weight": 20
          },
          {
            "topic_id": 38,
            "topic_name": "Kubernetes",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 20
          },
          {
            "topic_id": 36,
            "topic_name": "CI/CD Pipelines",
            "difficulty_strategy": "dynamic",
            "allowed_difficulties": ["easy", "medium"],
            "weight": 20
          },
          {
            "topic_id": 39,
            "topic_name": "AWS",
            "difficulty_strategy": "fixed",
            "difficulty": "medium",
            "weight": 20
          },
          {
            "topic_id": 42,
            "topic_name": "Infrastructure as Code",
            "difficulty_strategy": "fixed",
            "difficulty": "medium",
            "weight": 20
          }
        ]
      },

      "coding_round": {
        "enabled": false,
        "question_count": 2,
        "max_duration_minutes": 20,
        "weight": 25,

        "problems": [
          {
            "difficulty": "easy",
            "topics": ["shell_scripting", "automation"],
            "estimated_time_minutes": 8,
            "weight": 40
          },
          {
            "difficulty": "medium",
            "topics": ["infrastructure_automation", "containerization"],
            "estimated_time_minutes": 12,
            "weight": 60
          }
        ],

        "execution_config": {
          "languages_allowed": ["python3", "bash", "go"],
          "time_limit_ms": 3000,
          "memory_limit_kb": 262144
        },

        "scoring": {
          "correctness_weight": 70,
          "code_quality_weight": 30,
          "minimum_pass_percentage": 50
        }
      },

      "complexity_analysis": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 4,
        "weight": 10,
        "expectations": ["time_complexity", "space_complexity"]
      },

      "behavioral": {
        "enabled": true,
        "question_count": 1,
        "max_duration_minutes": 5,
        "weight": 10,
        "topics": ["incident_response", "collaboration", "automation_mindset"]
      }
    },

    "scoring": {
      "strategy": "weighted_sum",
      "normalization": "percentage",
      "pass_threshold": 60,
      "section_weights": {
        "resume_analysis": 10,
        "self_introduction": 5,
        "topics_assessment": 30,
        "coding_round": 25,
        "complexity_analysis": 10,
        "behavioral": 10,
        "bonus_points": 10
      }
    },

    "proctoring": {
      "enabled": true,
      "advisory_only": true,
      "basic_monitoring": ["tab_switch", "face_detection"]
    },

    "settings": {
      "auto_submit_on_timeout": true,
      "allow_resume_session": false,
      "show_progress": true
    }
  }'::jsonb,
 NULL,
 60,
 1,
 true
)

ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- PART 2: Map templates to roles in interview_template_roles table
-- ============================================================================

INSERT INTO public.interview_template_roles (interview_template_id, role_id)
VALUES
    -- DSA Fundamentals (template_id=1) - Relevant for all developer roles
    (1, 1),   -- Backend Developer
    (1, 2),   -- Frontend Developer
    (1, 3),   -- Full Stack Developer
    (1, 5),   -- Data Engineer
    (1, 6),   -- Mobile App Developer
    (1, 7),   -- ML Engineer

    -- System Design (template_id=2) - Senior-level architecture roles
    (2, 1),   -- Backend Developer
    (2, 3),   -- Full Stack Developer
    (2, 4),   -- DevOps Engineer
    (2, 5),   -- Data Engineer

    -- Backend Engineering (template_id=3) - Backend-focused roles
    (3, 1),   -- Backend Developer
    (3, 3),   -- Full Stack Developer

    -- Frontend Development (template_id=4) - Frontend-focused roles
    (4, 2),   -- Frontend Developer
    (4, 3),   -- Full Stack Developer

    -- Behavioral Interview (template_id=5) - All roles
    (5, 1),   -- Backend Developer
    (5, 2),   -- Frontend Developer
    (5, 3),   -- Full Stack Developer
    (5, 4),   -- DevOps Engineer
    (5, 5),   -- Data Engineer
    (5, 6),   -- Mobile App Developer
    (5, 7),   -- ML Engineer

    -- DevOps & Cloud (template_id=6) - Infrastructure roles
    (6, 4),   -- DevOps Engineer
    (6, 1),   -- Backend Developer
    (6, 3)    -- Full Stack Developer

ON CONFLICT (interview_template_id, role_id) DO NOTHING;

-- ============================================================================
-- PART 3: Update sequence to continue from ID 7
-- ============================================================================

-- Ensure the sequence starts from 7 for future template insertions
SELECT setval('public.interview_templates_id_seq', 6, true);
