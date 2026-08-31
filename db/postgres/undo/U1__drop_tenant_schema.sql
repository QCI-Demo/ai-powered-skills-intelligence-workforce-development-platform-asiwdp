-- Undo V1 tenant provisioning schema
DROP TABLE IF EXISTS idempotency_record;
DROP TABLE IF EXISTS tenant_metadata;
DROP TABLE IF EXISTS tenant_configuration;
DROP TABLE IF EXISTS tenant;
