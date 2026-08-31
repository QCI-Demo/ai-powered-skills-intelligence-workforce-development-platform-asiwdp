/**
 * Create ASIWDP MongoDB collections for tenant provisioning.
 *
 * Usage (mongosh):
 *   mongosh "$MONGODB_URI" db/mongodb/init/create_tenant_collections.js
 *
 * Collections are partitioned by tenant_id (leading index / shard key).
 */

const dbName =
  typeof process !== "undefined" && process.env.MONGODB_DB
    ? process.env.MONGODB_DB
    : "asiwdp_tenants";

const target = db.getSiblingDB(dbName);

function ensureCollection(name, validator, indexes) {
  const existing = target.getCollectionNames();
  if (!existing.includes(name)) {
    target.createCollection(name, { validator });
  } else {
    try {
      target.runCommand({ collMod: name, validator, validationLevel: "moderate" });
    } catch (e) {
      print(`collMod skipped for ${name}: ${e}`);
    }
  }
  for (const idx of indexes) {
    target.getCollection(name).createIndex(idx.keys, idx.options || {});
  }
}

ensureCollection(
  "tenants",
  {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "slug", "display_name", "status"],
      properties: {
        _id: { bsonType: ["objectId", "string"] },
        tenant_id: {
          bsonType: "string",
          pattern:
            "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        },
        slug: {
          bsonType: "string",
          pattern: "^[a-z0-9]([a-z0-9-]{0,126}[a-z0-9])?$",
        },
        display_name: { bsonType: "string", minLength: 1, maxLength: 255 },
        status: {
          enum: ["pending", "active", "suspended", "decommissioned"],
        },
        plan_code: { bsonType: "string" },
        region: { bsonType: "string" },
        timezone: { bsonType: "string" },
        contact: { bsonType: "object" },
        provisioned_at: { bsonType: "date" },
        created_at: { bsonType: "date" },
        updated_at: { bsonType: "date" },
        created_by: { bsonType: "string" },
      },
      additionalProperties: false,
    },
  },
  [
    { keys: { tenant_id: 1 }, options: { unique: true, name: "uq_tenant_id" } },
    { keys: { slug: 1 }, options: { unique: true, name: "uq_slug" } },
    { keys: { status: 1 }, options: { name: "idx_status" } },
  ]
);

ensureCollection(
  "tenant_configurations",
  {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "config_key", "config_value", "version"],
      properties: {
        _id: { bsonType: ["objectId", "string"] },
        tenant_id: {
          bsonType: "string",
          pattern:
            "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        },
        config_key: { bsonType: "string", minLength: 1, maxLength: 128 },
        config_value: {},
        is_default: { bsonType: "bool" },
        version: { bsonType: "int", minimum: 1 },
        created_at: { bsonType: "date" },
        updated_at: { bsonType: "date" },
      },
      additionalProperties: false,
    },
  },
  [
    {
      keys: { tenant_id: 1, config_key: 1 },
      options: { unique: true, name: "uq_tenant_config_key" },
    },
    { keys: { tenant_id: 1 }, options: { name: "idx_tenant_id" } },
  ]
);

ensureCollection(
  "tenant_metadata",
  {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "meta_key", "meta_value"],
      properties: {
        _id: { bsonType: ["objectId", "string"] },
        tenant_id: {
          bsonType: "string",
          pattern:
            "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        },
        meta_key: { bsonType: "string", minLength: 1, maxLength: 128 },
        meta_value: { bsonType: "object" },
        tags: { bsonType: "array", items: { bsonType: "string" } },
        created_at: { bsonType: "date" },
        updated_at: { bsonType: "date" },
      },
      additionalProperties: false,
    },
  },
  [
    {
      keys: { tenant_id: 1, meta_key: 1 },
      options: { unique: true, name: "uq_tenant_meta_key" },
    },
    { keys: { tenant_id: 1 }, options: { name: "idx_tenant_id" } },
  ]
);

print(`ASIWDP tenant collections ready in database '${dbName}'`);
