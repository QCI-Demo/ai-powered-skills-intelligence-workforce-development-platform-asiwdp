/**
 * Create ASIWDP MongoDB collections with JSON Schema validation and indexes.
 *
 * Usage (mongosh):
 *   mongosh "$MONGODB_URI" db/mongodb/init/create_collections.js
 *
 * Idempotent: drops validators/indexes only when recreating via ensure path
 * in the Python data-access layer; this script uses createCollection with
 * collMod fallback.
 */

const dbName = typeof process !== "undefined" && process.env.MONGODB_DB
  ? process.env.MONGODB_DB
  : "asiwdp_skills";

const target = db.getSiblingDB(dbName);

const skillMetaValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["tenant_id", "skill_id", "version"],
    properties: {
      _id: { bsonType: ["objectId", "string"] },
      tenant_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
      },
      skill_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
      },
      version: { bsonType: "int", minimum: 1 },
      metadata: { bsonType: "object" },
      tags: { bsonType: "array", items: { bsonType: "string" } },
      audit_entries: {
        bsonType: "array",
        items: {
          bsonType: "object",
          required: ["action", "at"],
          properties: {
            action: { bsonType: "string" },
            at: { bsonType: "date" },
            actor_id: { bsonType: ["string", "null"] },
            detail: { bsonType: "object" }
          }
        }
      },
      created_at: { bsonType: "date" },
      updated_at: { bsonType: "date" }
    },
    additionalProperties: false
  }
};

const roleMetaValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["tenant_id", "role_id", "version"],
    properties: {
      _id: { bsonType: ["objectId", "string"] },
      tenant_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
      },
      role_id: {
        bsonType: "string",
        pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
      },
      version: { bsonType: "int", minimum: 1 },
      metadata: { bsonType: "object" },
      tags: { bsonType: "array", items: { bsonType: "string" } },
      audit_entries: {
        bsonType: "array",
        items: {
          bsonType: "object",
          required: ["action", "at"],
          properties: {
            action: { bsonType: "string" },
            at: { bsonType: "date" },
            actor_id: { bsonType: ["string", "null"] },
            detail: { bsonType: "object" }
          }
        }
      },
      created_at: { bsonType: "date" },
      updated_at: { bsonType: "date" }
    },
    additionalProperties: false
  }
};

function ensureCollection(name, validator) {
  const existing = target.getCollectionNames();
  if (!existing.includes(name)) {
    target.createCollection(name, {
      validator: validator,
      validationLevel: "moderate",
      validationAction: "error"
    });
    print(`Created collection ${name}`);
  } else {
    target.runCommand({
      collMod: name,
      validator: validator,
      validationLevel: "moderate",
      validationAction: "error"
    });
    print(`Updated validator on ${name}`);
  }
}

ensureCollection("skill_meta", skillMetaValidator);
ensureCollection("role_meta", roleMetaValidator);

target.skill_meta.createIndex(
  { tenant_id: 1, skill_id: 1, version: 1 },
  { unique: true, name: "uq_skill_meta_tenant_skill_version" }
);
target.skill_meta.createIndex(
  { tenant_id: 1, version: 1 },
  { name: "idx_skill_meta_tenant_version" }
);

target.role_meta.createIndex(
  { tenant_id: 1, role_id: 1, version: 1 },
  { unique: true, name: "uq_role_meta_tenant_role_version" }
);
target.role_meta.createIndex(
  { tenant_id: 1, version: 1 },
  { name: "idx_role_meta_tenant_version" }
);

print("MongoDB skill_meta / role_meta collections ready.");
