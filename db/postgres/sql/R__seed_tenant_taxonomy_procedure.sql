-- Repeatable migration: idempotent helper to seed a baseline taxonomy
-- for any new tenant (call from provisioning after tenant create).
--
-- Usage:
--   SELECT asiwdp_seed_tenant_taxonomy('22222222-2222-2222-2222-222222222222', 1);

CREATE OR REPLACE FUNCTION asiwdp_seed_tenant_taxonomy(
    p_tenant_id UUID,
    p_version INTEGER DEFAULT 1
) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_version < 1 THEN
        RAISE EXCEPTION 'version must be >= 1';
    END IF;

    INSERT INTO proficiency (tenant_id, version, level, code, name, description, rank_order)
    VALUES
        (p_tenant_id, p_version, 1, 'AWARE', 'Awareness',
         'Familiar with concepts; requires guidance.', 1),
        (p_tenant_id, p_version, 2, 'WORKING', 'Working',
         'Applies skill independently on routine tasks.', 2),
        (p_tenant_id, p_version, 3, 'PROFICIENT', 'Proficient',
         'Handles complex situations; mentors others.', 3),
        (p_tenant_id, p_version, 4, 'EXPERT', 'Expert',
         'Sets standards and drives organizational practice.', 4)
    ON CONFLICT (tenant_id, code, version) DO NOTHING;

    INSERT INTO skill (tenant_id, version, code, name, description, category, status)
    VALUES
        (p_tenant_id, p_version, 'DATA-LITERACY', 'Data Literacy',
         'Interpret, analyze, and communicate with data.', 'Foundational', 'active'),
        (p_tenant_id, p_version, 'PYTHON', 'Python Programming',
         'Write maintainable Python for data and services.', 'Technical', 'active'),
        (p_tenant_id, p_version, 'STAKEHOLDER-COMMS', 'Stakeholder Communication',
         'Translate technical insights for business audiences.', 'Behavioral', 'active')
    ON CONFLICT (tenant_id, code, version) DO NOTHING;

    -- Parent-linked SQL skill (after DATA-LITERACY exists)
    INSERT INTO skill (
        tenant_id, version, code, name, description, category, parent_skill_id, status
    )
    SELECT
        p_tenant_id,
        p_version,
        'SQL',
        'SQL & Relational Modeling',
        'Query and model relational data effectively.',
        'Technical',
        s.id,
        'active'
    FROM skill s
    WHERE s.tenant_id = p_tenant_id
      AND s.version = p_version
      AND s.code = 'DATA-LITERACY'
    ON CONFLICT (tenant_id, code, version) DO NOTHING;

    INSERT INTO role (tenant_id, version, code, name, description, family, status)
    VALUES
        (p_tenant_id, p_version, 'DATA-ANALYST', 'Data Analyst',
         'Analyzes datasets and delivers actionable insights.', 'Analytics', 'active'),
        (p_tenant_id, p_version, 'ML-ENGINEER', 'Machine Learning Engineer',
         'Builds and operates ML systems in production.', 'Engineering', 'active')
    ON CONFLICT (tenant_id, code, version) DO NOTHING;

    INSERT INTO competency_requirement (
        tenant_id, version, role_id, skill_id, proficiency_id, is_required, weight
    )
    SELECT
        p_tenant_id,
        p_version,
        r.id,
        s.id,
        p.id,
        TRUE,
        1.00
    FROM role r
    JOIN skill s
      ON s.tenant_id = r.tenant_id
     AND s.version = r.version
     AND s.code = 'DATA-LITERACY'
    JOIN proficiency p
      ON p.tenant_id = r.tenant_id
     AND p.version = r.version
     AND p.code = 'PROFICIENT'
    WHERE r.tenant_id = p_tenant_id
      AND r.version = p_version
      AND r.code = 'DATA-ANALYST'
    ON CONFLICT (tenant_id, role_id, skill_id, version) DO NOTHING;

    INSERT INTO audit_log (
        tenant_id, version, entity_type, entity_id, action, change_blob
    )
    SELECT
        p_tenant_id,
        p_version,
        'taxonomy',
        p_tenant_id,
        'IMPORT',
        jsonb_build_object(
            'source', 'asiwdp_seed_tenant_taxonomy',
            'version', p_version
        )
    WHERE NOT EXISTS (
        SELECT 1
          FROM audit_log a
         WHERE a.tenant_id = p_tenant_id
           AND a.version = p_version
           AND a.entity_type = 'taxonomy'
           AND a.action = 'IMPORT'
           AND a.change_blob->>'source' = 'asiwdp_seed_tenant_taxonomy'
    );
END;
$$;
