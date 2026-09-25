/**
 * ASIWDP Tenant Provisioning Schema - MongoDB Collection Schema
 * Story: Build Automated Tenant Provisioning and Configuration Service
 * Task: 89d8dbba-19a6-4a35-8382-d1be49c1fcf0
 * 
 * This file defines JSON Schema validators and indexes for MongoDB collections.
 * Run with: mongosh < mongodb_schema.js
 */

// =============================================================================
// Database Setup
// =============================================================================

use asiwdp;

// =============================================================================
// Collection: tenants
// =============================================================================

db.createCollection("tenants", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["_id", "name", "slug", "status", "tier", "contactEmail", "createdAt", "updatedAt"],
            properties: {
                _id: {
                    bsonType: "binData",
                    description: "UUID - tenant_id as partition key"
                },
                name: {
                    bsonType: "string",
                    minLength: 1,
                    maxLength: 255,
                    description: "Tenant name"
                },
                slug: {
                    bsonType: "string",
                    minLength: 3,
                    maxLength: 100,
                    pattern: "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
                    description: "URL-safe identifier"
                },
                displayName: {
                    bsonType: ["string", "null"],
                    maxLength: 255,
                    description: "Optional friendly display name"
                },
                status: {
                    enum: ["provisioning", "active", "suspended", "deprovisioning", "deleted"],
                    description: "Tenant lifecycle status"
                },
                tier: {
                    enum: ["free", "standard", "professional", "enterprise"],
                    description: "Subscription tier"
                },
                ownerUserId: {
                    bsonType: ["binData", "null"],
                    description: "UUID of initial admin user"
                },
                contactEmail: {
                    bsonType: "string",
                    pattern: "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$",
                    description: "Primary contact email"
                },
                metadata: {
                    bsonType: "object",
                    description: "Extensible attributes"
                },
                createdAt: {
                    bsonType: "date",
                    description: "Creation timestamp"
                },
                updatedAt: {
                    bsonType: "date",
                    description: "Last update timestamp"
                },
                provisionedAt: {
                    bsonType: ["date", "null"],
                    description: "Provisioning completion timestamp"
                },
                provisionedBy: {
                    bsonType: ["binData", "null"],
                    description: "UUID of user who initiated provisioning"
                }
            },
            additionalProperties: false
        }
    },
    validationLevel: "strict",
    validationAction: "error"
});

// Tenants indexes
db.tenants.createIndex({ "name": 1 }, { unique: true });
db.tenants.createIndex({ "slug": 1 }, { unique: true });
db.tenants.createIndex({ "status": 1 });
db.tenants.createIndex({ "tier": 1 });
db.tenants.createIndex({ "createdAt": 1 });
db.tenants.createIndex({ "contactEmail": 1 });

// =============================================================================
// Collection: tenantConfigurations
// =============================================================================

db.createCollection("tenantConfigurations", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["_id", "tenantId", "configKey", "configValue", "isDefault", "createdAt", "updatedAt"],
            properties: {
                _id: {
                    bsonType: "binData",
                    description: "UUID - config_id"
                },
                tenantId: {
                    bsonType: "binData",
                    description: "UUID - references tenants"
                },
                configKey: {
                    bsonType: "string",
                    minLength: 1,
                    maxLength: 255,
                    description: "Configuration key"
                },
                configValue: {
                    description: "Configuration value (any BSON type)"
                },
                isDefault: {
                    bsonType: "bool",
                    description: "Whether using default value"
                },
                createdAt: {
                    bsonType: "date",
                    description: "Creation timestamp"
                },
                updatedAt: {
                    bsonType: "date",
                    description: "Last update timestamp"
                }
            },
            additionalProperties: false
        }
    },
    validationLevel: "strict",
    validationAction: "error"
});

// Tenant configurations indexes
db.tenantConfigurations.createIndex({ "tenantId": 1 });
db.tenantConfigurations.createIndex({ "tenantId": 1, "configKey": 1 }, { unique: true });

// =============================================================================
// Collection: tenantMetadata
// =============================================================================

db.createCollection("tenantMetadata", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["_id", "tenantId", "key", "value", "scope", "createdAt", "updatedAt"],
            properties: {
                _id: {
                    bsonType: "binData",
                    description: "UUID - metadata_id"
                },
                tenantId: {
                    bsonType: "binData",
                    description: "UUID - references tenants"
                },
                key: {
                    bsonType: "string",
                    minLength: 1,
                    maxLength: 255,
                    description: "Metadata key"
                },
                value: {
                    description: "Metadata value (any BSON type)"
                },
                scope: {
                    bsonType: "string",
                    maxLength: 100,
                    description: "Metadata scope/category"
                },
                createdAt: {
                    bsonType: "date",
                    description: "Creation timestamp"
                },
                updatedAt: {
                    bsonType: "date",
                    description: "Last update timestamp"
                }
            },
            additionalProperties: false
        }
    },
    validationLevel: "strict",
    validationAction: "error"
});

// Tenant metadata indexes
db.tenantMetadata.createIndex({ "tenantId": 1 });
db.tenantMetadata.createIndex({ "tenantId": 1, "key": 1, "scope": 1 }, { unique: true });

// =============================================================================
// Collection: idempotencyKeys
// =============================================================================

db.createCollection("idempotencyKeys", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["_id", "requestHash", "response", "createdAt", "expiresAt"],
            properties: {
                _id: {
                    bsonType: "string",
                    description: "Idempotency key (client-provided)"
                },
                tenantId: {
                    bsonType: ["binData", "null"],
                    description: "UUID of created tenant (if successful)"
                },
                requestHash: {
                    bsonType: "string",
                    minLength: 64,
                    maxLength: 64,
                    description: "SHA-256 hash of request body"
                },
                response: {
                    bsonType: "object",
                    description: "Cached response"
                },
                createdAt: {
                    bsonType: "date",
                    description: "Creation timestamp"
                },
                expiresAt: {
                    bsonType: "date",
                    description: "TTL for cleanup"
                }
            },
            additionalProperties: false
        }
    },
    validationLevel: "strict",
    validationAction: "error"
});

// Idempotency keys indexes with TTL
db.idempotencyKeys.createIndex({ "expiresAt": 1 }, { expireAfterSeconds: 0 });
db.idempotencyKeys.createIndex({ "tenantId": 1 }, { sparse: true });

// =============================================================================
// Collection: tenantProvisioningEvents
// =============================================================================

db.createCollection("tenantProvisioningEvents", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["_id", "tenantId", "eventType", "payload", "emittedAt", "status"],
            properties: {
                _id: {
                    bsonType: "binData",
                    description: "UUID - event_id"
                },
                tenantId: {
                    bsonType: "binData",
                    description: "UUID - references tenants"
                },
                eventType: {
                    enum: [
                        "tenant.provisioning.started",
                        "tenant.provisioning.completed",
                        "tenant.provisioning.failed",
                        "tenant.configuration.initialized",
                        "tenant.status.changed",
                        "tenant.tier.changed"
                    ],
                    description: "Event type"
                },
                payload: {
                    bsonType: "object",
                    description: "Event details"
                },
                emittedAt: {
                    bsonType: "date",
                    description: "Emission timestamp"
                },
                status: {
                    enum: ["pending", "delivered", "failed", "retry"],
                    description: "Event delivery status"
                }
            },
            additionalProperties: false
        }
    },
    validationLevel: "strict",
    validationAction: "error"
});

// Provisioning events indexes
db.tenantProvisioningEvents.createIndex({ "tenantId": 1 });
db.tenantProvisioningEvents.createIndex({ "emittedAt": 1 });
db.tenantProvisioningEvents.createIndex({ "eventType": 1 });
db.tenantProvisioningEvents.createIndex({ "status": 1 }, { partialFilterExpression: { status: { $ne: "delivered" } } });

print("ASIWDP Tenant Provisioning MongoDB schema created successfully.");
