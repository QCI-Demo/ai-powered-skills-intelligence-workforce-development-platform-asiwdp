/**
 * ASIWDP Tenant Provisioning Schema - MongoDB Collection Schemas
 * Version: 1.0.0
 * 
 * This file defines JSON Schema validators and indexes for MongoDB collections
 * supporting the tenant provisioning service. All collections use tenant_id
 * as a partition key for data isolation.
 */

// ============================================================================
// DATABASE SETUP
// ============================================================================

// Use the asiwdp database
use asiwdp;

// ============================================================================
// TENANTS COLLECTION
// ============================================================================

db.createCollection("tenants", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "name", "status", "planTier", "createdAt", "createdBy"],
      properties: {
        _id: {
          bsonType: "string",
          description: "UUID tenant identifier (partition key)"
        },
        name: {
          bsonType: "string",
          minLength: 1,
          maxLength: 255,
          description: "Unique tenant name"
        },
        displayName: {
          bsonType: "string",
          maxLength: 500,
          description: "Human-readable display name"
        },
        domain: {
          bsonType: "string",
          maxLength: 255,
          description: "Custom domain for tenant"
        },
        status: {
          enum: ["pending", "active", "suspended", "deprovisioned", "failed"],
          description: "Current tenant status"
        },
        planTier: {
          enum: ["free", "starter", "professional", "enterprise", "custom"],
          description: "Subscription plan tier"
        },
        settings: {
          bsonType: "object",
          description: "Tenant-specific settings"
        },
        createdAt: {
          bsonType: "date",
          description: "Timestamp of creation"
        },
        updatedAt: {
          bsonType: "date",
          description: "Timestamp of last update"
        },
        createdBy: {
          bsonType: "string",
          description: "User ID who created the tenant"
        },
        provisionedAt: {
          bsonType: "date",
          description: "Timestamp when provisioning completed"
        },
        deprovisionedAt: {
          bsonType: "date",
          description: "Timestamp of deprovisioning"
        }
      }
    }
  }
});

// Indexes for tenants collection
db.tenants.createIndex({ "name": 1 }, { unique: true });
db.tenants.createIndex({ "domain": 1 }, { unique: true, sparse: true });
db.tenants.createIndex({ "status": 1 });
db.tenants.createIndex({ "planTier": 1 });
db.tenants.createIndex({ "createdAt": 1 });

// ============================================================================
// TENANT CONFIGURATIONS COLLECTION
// ============================================================================

db.createCollection("tenantConfigurations", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenantId", "configKey", "configValue", "category", "isActive", "version", "createdAt"],
      properties: {
        _id: {
          bsonType: "objectId"
        },
        tenantId: {
          bsonType: "string",
          description: "Reference to tenant (partition key)"
        },
        configKey: {
          bsonType: "string",
          minLength: 1,
          maxLength: 255,
          description: "Configuration key name"
        },
        configValue: {
          description: "Configuration value (any type)"
        },
        category: {
          enum: ["general", "security", "integration", "feature_flags", "branding", "notifications", "compliance"],
          description: "Configuration category"
        },
        isActive: {
          bsonType: "bool",
          description: "Whether config is currently active"
        },
        version: {
          bsonType: "int",
          minimum: 1,
          description: "Version number for optimistic locking"
        },
        createdAt: {
          bsonType: "date"
        },
        updatedAt: {
          bsonType: "date"
        }
      }
    }
  }
});

// Indexes for tenant configurations
db.tenantConfigurations.createIndex({ "tenantId": 1, "configKey": 1 }, { unique: true });
db.tenantConfigurations.createIndex({ "tenantId": 1, "category": 1 });
db.tenantConfigurations.createIndex({ "tenantId": 1, "isActive": 1 });

// ============================================================================
// TENANT METADATA COLLECTION
// ============================================================================

db.createCollection("tenantMetadata", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenantId", "metadataKey", "metadataValue", "createdAt"],
      properties: {
        _id: {
          bsonType: "objectId"
        },
        tenantId: {
          bsonType: "string",
          description: "Reference to tenant (partition key)"
        },
        metadataKey: {
          bsonType: "string",
          minLength: 1,
          maxLength: 255,
          description: "Metadata key"
        },
        metadataValue: {
          bsonType: "string",
          description: "Metadata value"
        },
        createdAt: {
          bsonType: "date"
        },
        updatedAt: {
          bsonType: "date"
        }
      }
    }
  }
});

// Indexes for tenant metadata
db.tenantMetadata.createIndex({ "tenantId": 1, "metadataKey": 1 }, { unique: true });
db.tenantMetadata.createIndex({ "tenantId": 1 });

// ============================================================================
// IDEMPOTENCY KEYS COLLECTION
// ============================================================================

db.createCollection("idempotencyKeys", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "requestHash", "responseBody", "statusCode", "createdAt", "expiresAt"],
      properties: {
        _id: {
          bsonType: "string",
          description: "Idempotency key (primary key)"
        },
        tenantId: {
          bsonType: "string",
          description: "Associated tenant ID"
        },
        requestHash: {
          bsonType: "string",
          minLength: 64,
          maxLength: 64,
          description: "SHA-256 hash of request body"
        },
        responseBody: {
          bsonType: "object",
          description: "Cached response body"
        },
        statusCode: {
          bsonType: "int",
          minimum: 100,
          maximum: 599,
          description: "HTTP status code of cached response"
        },
        createdAt: {
          bsonType: "date"
        },
        expiresAt: {
          bsonType: "date"
        }
      }
    }
  }
});

// TTL index for automatic cleanup
db.idempotencyKeys.createIndex({ "expiresAt": 1 }, { expireAfterSeconds: 0 });

// ============================================================================
// PROVISIONING EVENTS COLLECTION
// ============================================================================

db.createCollection("provisioningEvents", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenantId", "eventType", "eventPayload", "status", "createdAt"],
      properties: {
        _id: {
          bsonType: "objectId"
        },
        tenantId: {
          bsonType: "string",
          description: "Reference to tenant (partition key)"
        },
        eventType: {
          bsonType: "string",
          minLength: 1,
          maxLength: 100,
          description: "Type of provisioning event"
        },
        eventPayload: {
          bsonType: "object",
          description: "Event data"
        },
        status: {
          enum: ["pending", "published", "failed", "acknowledged"],
          description: "Event processing status"
        },
        publishedAt: {
          bsonType: "date",
          description: "When event was published"
        },
        createdAt: {
          bsonType: "date"
        }
      }
    }
  }
});

// Indexes for provisioning events
db.provisioningEvents.createIndex({ "tenantId": 1, "eventType": 1 });
db.provisioningEvents.createIndex({ "status": 1 }, { partialFilterExpression: { status: "pending" } });
db.provisioningEvents.createIndex({ "createdAt": 1 });

// ============================================================================
// TENANT AUDIT LOGS COLLECTION
// ============================================================================

db.createCollection("tenantAuditLogs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenantId", "action", "actorId", "actorType", "resourceType", "createdAt"],
      properties: {
        _id: {
          bsonType: "objectId"
        },
        tenantId: {
          bsonType: "string",
          description: "Reference to tenant (partition key)"
        },
        action: {
          bsonType: "string",
          minLength: 1,
          maxLength: 100,
          description: "Action performed"
        },
        actorId: {
          bsonType: "string",
          description: "ID of the actor (user/service)"
        },
        actorType: {
          bsonType: "string",
          description: "Type of actor"
        },
        resourceType: {
          bsonType: "string",
          description: "Type of resource affected"
        },
        resourceId: {
          bsonType: "string",
          description: "ID of resource affected"
        },
        changes: {
          bsonType: "object",
          description: "Before/after state changes"
        },
        createdAt: {
          bsonType: "date"
        }
      }
    }
  }
});

// Indexes for audit logs
db.tenantAuditLogs.createIndex({ "tenantId": 1, "createdAt": -1 });
db.tenantAuditLogs.createIndex({ "actorId": 1 });
db.tenantAuditLogs.createIndex({ "resourceType": 1, "resourceId": 1 });

// ============================================================================
// DEFAULT CONFIGURATION TEMPLATE
// ============================================================================

/**
 * Default configuration template to be inserted when a new tenant is created.
 * This is stored as a reference document in a separate collection.
 */
db.createCollection("configurationTemplates");

db.configurationTemplates.insertOne({
  _id: "default_tenant_config",
  version: "1.0.0",
  configurations: [
    // General settings
    { configKey: "max_users", configValue: 100, category: "general" },
    { configKey: "max_organizations", configValue: 10, category: "general" },
    { configKey: "timezone", configValue: "UTC", category: "general" },
    { configKey: "locale", configValue: "en-US", category: "general" },
    
    // Security settings
    { configKey: "session_timeout_minutes", configValue: 60, category: "security" },
    { configKey: "mfa_required", configValue: false, category: "security" },
    { configKey: "password_policy", configValue: { min_length: 8, require_uppercase: true, require_number: true }, category: "security" },
    { configKey: "allowed_ip_ranges", configValue: [], category: "security" },
    
    // Feature flags
    { configKey: "skills_ai_enabled", configValue: true, category: "feature_flags" },
    { configKey: "learning_paths_enabled", configValue: true, category: "feature_flags" },
    { configKey: "analytics_dashboard_enabled", configValue: true, category: "feature_flags" },
    { configKey: "api_access_enabled", configValue: false, category: "feature_flags" },
    
    // Compliance settings
    { configKey: "data_retention_days", configValue: 365, category: "compliance" },
    { configKey: "gdpr_enabled", configValue: true, category: "compliance" },
    { configKey: "audit_logging_enabled", configValue: true, category: "compliance" },
    
    // Notification settings
    { configKey: "email_notifications_enabled", configValue: true, category: "notifications" },
    { configKey: "webhook_url", configValue: null, category: "notifications" }
  ],
  createdAt: new Date()
});

print("MongoDB schema for tenant provisioning has been created successfully.");
