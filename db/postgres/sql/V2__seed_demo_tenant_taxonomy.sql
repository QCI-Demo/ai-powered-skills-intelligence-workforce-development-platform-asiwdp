-- Idempotent seed of an initial taxonomy version for the demo tenant.
-- Story task: 990ffe8b-8e74-40e5-8669-e385653fc17e
--
-- Re-running this migration is safe: all inserts use ON CONFLICT DO NOTHING
-- and fixed UUIDs so the seed is deterministic.

-- Demo tenant used for local/dev bootstrap only (not production PII).
-- tenant_id: 22222222-2222-2222-2222-222222222222
-- taxonomy version: 1

-- ---------------------------------------------------------------------------
-- Proficiency scale (v1)
-- ---------------------------------------------------------------------------
INSERT INTO proficiency (id, tenant_id, version, level, code, name, description, rank_order)
VALUES
    ('a1000001-0000-4000-8000-000000000001',
     '22222222-2222-2222-2222-222222222222', 1, 1, 'AWARE',
     'Awareness', 'Familiar with concepts; requires guidance.', 1),
    ('a1000001-0000-4000-8000-000000000002',
     '22222222-2222-2222-2222-222222222222', 1, 2, 'WORKING',
     'Working', 'Applies skill independently on routine tasks.', 2),
    ('a1000001-0000-4000-8000-000000000003',
     '22222222-2222-2222-2222-222222222222', 1, 3, 'PROFICIENT',
     'Proficient', 'Handles complex situations; mentors others.', 3),
    ('a1000001-0000-4000-8000-000000000004',
     '22222222-2222-2222-2222-222222222222', 1, 4, 'EXPERT',
     'Expert', 'Sets standards and drives organizational practice.', 4)
ON CONFLICT (tenant_id, code, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Skills (v1)
-- ---------------------------------------------------------------------------
INSERT INTO skill (id, tenant_id, version, code, name, description, category, parent_skill_id, status)
VALUES
    ('b2000001-0000-4000-8000-000000000001',
     '22222222-2222-2222-2222-222222222222', 1, 'DATA-LITERACY',
     'Data Literacy', 'Interpret, analyze, and communicate with data.',
     'Foundational', NULL, 'active'),
    ('b2000001-0000-4000-8000-000000000002',
     '22222222-2222-2222-2222-222222222222', 1, 'PYTHON',
     'Python Programming', 'Write maintainable Python for data and services.',
     'Technical', NULL, 'active'),
    ('b2000001-0000-4000-8000-000000000003',
     '22222222-2222-2222-2222-222222222222', 1, 'SQL',
     'SQL & Relational Modeling', 'Query and model relational data effectively.',
     'Technical', 'b2000001-0000-4000-8000-000000000001', 'active'),
    ('b2000001-0000-4000-8000-000000000004',
     '22222222-2222-2222-2222-222222222222', 1, 'STAKEHOLDER-COMMS',
     'Stakeholder Communication', 'Translate technical insights for business audiences.',
     'Behavioral', NULL, 'active')
ON CONFLICT (tenant_id, code, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Roles (v1)
-- ---------------------------------------------------------------------------
INSERT INTO role (id, tenant_id, version, code, name, description, family, status)
VALUES
    ('c3000001-0000-4000-8000-000000000001',
     '22222222-2222-2222-2222-222222222222', 1, 'DATA-ANALYST',
     'Data Analyst', 'Analyzes datasets and delivers actionable insights.',
     'Analytics', 'active'),
    ('c3000001-0000-4000-8000-000000000002',
     '22222222-2222-2222-2222-222222222222', 1, 'ML-ENGINEER',
     'Machine Learning Engineer', 'Builds and operates ML systems in production.',
     'Engineering', 'active')
ON CONFLICT (tenant_id, code, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Competency requirements (v1)
-- ---------------------------------------------------------------------------
INSERT INTO competency_requirement (
    id, tenant_id, version, role_id, skill_id, proficiency_id, is_required, weight
)
VALUES
    -- Data Analyst
    ('d4000001-0000-4000-8000-000000000001',
     '22222222-2222-2222-2222-222222222222', 1,
     'c3000001-0000-4000-8000-000000000001',
     'b2000001-0000-4000-8000-000000000001',
     'a1000001-0000-4000-8000-000000000003', TRUE, 1.00),
    ('d4000001-0000-4000-8000-000000000002',
     '22222222-2222-2222-2222-222222222222', 1,
     'c3000001-0000-4000-8000-000000000001',
     'b2000001-0000-4000-8000-000000000003',
     'a1000001-0000-4000-8000-000000000003', TRUE, 1.00),
    ('d4000001-0000-4000-8000-000000000003',
     '22222222-2222-2222-2222-222222222222', 1,
     'c3000001-0000-4000-8000-000000000001',
     'b2000001-0000-4000-8000-000000000004',
     'a1000001-0000-4000-8000-000000000002', TRUE, 0.75),
    -- ML Engineer
    ('d4000001-0000-4000-8000-000000000004',
     '22222222-2222-2222-2222-222222222222', 1,
     'c3000001-0000-4000-8000-000000000002',
     'b2000001-0000-4000-8000-000000000002',
     'a1000001-0000-4000-8000-000000000003', TRUE, 1.00),
    ('d4000001-0000-4000-8000-000000000005',
     '22222222-2222-2222-2222-222222222222', 1,
     'c3000001-0000-4000-8000-000000000002',
     'b2000001-0000-4000-8000-000000000001',
     'a1000001-0000-4000-8000-000000000002', TRUE, 0.80)
ON CONFLICT (tenant_id, role_id, skill_id, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Seed audit entry (idempotent via fixed id)
-- ---------------------------------------------------------------------------
INSERT INTO audit_log (
    id, tenant_id, version, entity_type, entity_id, action, actor_id, change_blob
)
VALUES (
    'e5000001-0000-4000-8000-000000000001',
    '22222222-2222-2222-2222-222222222222',
    1,
    'taxonomy',
    '22222222-2222-2222-2222-222222222222',
    'IMPORT',
    NULL,
    jsonb_build_object(
        'source', 'flyway_seed',
        'migration', 'V2__seed_demo_tenant_taxonomy',
        'skills', 4,
        'roles', 2,
        'proficiency_levels', 4,
        'competency_requirements', 5
    )
)
ON CONFLICT (id) DO NOTHING;
