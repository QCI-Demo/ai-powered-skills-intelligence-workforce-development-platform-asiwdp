-- Undo V1: drop skill taxonomy schema (reverse dependency order)

DROP FUNCTION IF EXISTS asiwdp_seed_tenant_taxonomy(UUID, INTEGER);
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS competency_requirement CASCADE;
DROP TABLE IF EXISTS role CASCADE;
DROP TABLE IF EXISTS proficiency CASCADE;
DROP TABLE IF EXISTS skill CASCADE;
