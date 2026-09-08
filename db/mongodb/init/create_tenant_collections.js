/**
 * Create ASIWDP tenant provisioning MongoDB collections with validators + indexes.
 *
 * Usage (mongosh):
 *   mongosh "$MONGODB_URI" db/mongodb/init/create_tenant_collections.js
 *
 * Partition key on every collection: tenant_id
 */

const dbName =
  typeof process !== "undefined" && process.env.MONGODB_DB
    ? process.env.MONGODB_DB
    : "asiwdp_tenants";

const target = db.getSiblingDB(dbName);

function loadValidator(path) {
  // Validators are inlined below for self-contained init (paths documented in README).
  return null;
}

const tenantsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["tenant_id", "slug", "display_name", "status", "created_at"],
    properties: {
      _id: { bsonType: ["objectId", "string"] },
      tenant_id: {
        bsonType: "string",
        pattern:
          "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
      },
      slug: {
        bsonType: "string",
        minLength: 2,
        maxLength: 64,
        pattern: "^[a-z0-9][a-z0-9-]{1,62}$",
      },
      display_name: { bsonType: "string", minLength: 1, maxLength: 255 },
      status: {
        enum: ["provisioning", "active", "suspended", "decommissioned"],
      },
      plan_code: { bsonType: "string" },
      data_residency: { bsonType: "string" },
      created_by: { bsonType: ["string", "null"] },
      created_at: { bsonType: "date" },
      updated_at: { bsonType: "date" },
      provisioned_at: { bsonType: ["date", "null"] },
    },
    additionalProperties: false,
  },
};

const configurationsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["tenant_id", "defaults", "locale", "timezone", "schema_version"],
    properties: {
      _id: { bsonType: ["objectId", "string"] },
      tenant_id: {
        bsonType: "string",
        pattern:
          "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
      },
      defaults: { bsonType: "object" },
      locale: { bsonType: "string" },
      timezone: { bsonType: "string" },
      metering_enabled: { bsonType: "bool" },
      gdpr_enabled: { bsonType: "bool" },
      ccpa_enabled: { bsonType: "bool" },
      schema_version: { bsonType: "int", minimum: 1 },
      created_at: { bsonType: "date" },
      updated_at: { bsonType: "date" },
    },
    additionalProperties: false,
  },
};

const metadataValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["tenant_id", "meta_key", "meta_value", "created_at"],
    properties: {
      _id: { bsonType: ["objectId", "string"] },
      tenant_id: {
        bsonType: "string",
        pattern:
          "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
      },
      meta_key: { bsonType: "string", minLength: 1, maxLength: 128 },
      meta_value: { bsonType: "object" },
      created_by: { bsonType: ["string", "null"] },
      created_at: { bsonType: "date" },
      updated_at: { bsonType: "date" },
    },
    additionalProperties: false,
  },
};

const idempotencyValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: [
      "idempotency_key",
      "tenant_id",
      "request_hash",
      "response_status",
      "response_body",
      "created_at",
      "expires_at",
    ],
    properties: {
      _id: { bsonType: ["objectId", "string"] },
      idempotency_key: { bsonType: "string", minLength: 8, maxLength: 128 },
      tenant_id: {
        bsonType: "string",
        pattern:
          "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
      },
      request_hash: { bsonType: "string" },
      response_status: { bsonType: "int", minimum: 200, maximum: 599 },
      response_body: { bsonType: "object" },
      created_at: { bsonType: "date" },
      expires_at: { bsonType: "date" },
    },
    additionalProperties: false,
  },
};

function ensureCollection(name, validator) {
  const existing = target.getCollectionNames();
  if (!existing.includes(name)) {
    target.createCollection(name, {
      validator: validator,
      validationLevel: "moderate",
      validationAction: "error",
    });
    print(`Created collection ${name}`);
  } else {
    target.runCommand({
      collMod: name,
      validator: validator,
      validationLevel: "moderate",
      validationAction: "error",
    });
    print(`Updated validator for ${name}`);
  }
}

ensureCollection("tenants", tenantsValidator);
ensureCollection("tenant_configurations", configurationsValidator);
ensureCollection("tenant_metadata", metadataValidator);
ensureCollection("idempotency_records", idempotencyValidator);

// Partition-key and uniqueness indexes
target.tenants.createIndex({ tenant_id: 1 }, { unique: true, name: "uq_tenants_tenant_id" });
target.tenants.createIndex({ slug: 1 }, { unique: true, name: "uq_tenants_slug" });
target.tenants.createIndex({ status: 1 }, { name: "idx_tenants_status" });

target.tenant_configurations.createIndex(
  { tenant_id: 1 },
  { unique: true, name: "uq_tenant_configurations_tenant_id" }
);

target.tenant_metadata.createIndex({ tenant_id: 1 }, { name: "idx_tenant_metadata_tenant_id" });
target.tenant_metadata.createIndex(
  { tenant_id: 1, meta_key: 1 },
  { unique: true, name: "uq_tenant_metadata_tenant_key" }
);

target.idempotency_records.createIndex(
  { idempotency_key: 1 },
  { unique: true, name: "uq_idempotency_key" }
);
target.idempotency_records.createIndex(
  { tenant_id: 1 },
  { name: "idx_idempotency_tenant_id" }
);
target.idempotency_records.createIndex(
  { expires_at: 1 },
  { expireAfterSeconds: 0, name: "ttl_idempotency_expires_at" }
);

print(`Tenant provisioning collections ready in db=${dbName}`);
