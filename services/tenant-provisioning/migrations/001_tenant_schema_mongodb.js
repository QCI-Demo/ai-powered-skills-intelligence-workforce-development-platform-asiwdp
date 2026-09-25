// =============================================================================
// ASIWDP Tenant Provisioning MongoDB Schema
// Schema Version: 1.0.0
// =============================================================================

// Collection: tenants
// Primary partition key: _id (tenant_id)
db.createCollection("tenants", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "name", "slug", "status", "tier", "contactEmail", "createdAt", "updatedAt", "createdBy"],
      properties: {
        _id: {
          bsonType: "string",
          description: "UUID tenant identifier"
        },
        name: {
          bsonType: "string",
          minLength: 1,
          maxLength: 255,
          description: "Human-readable tenant name"
        },
        slug: {
          bsonType: "string",
          minLength: 3,
          maxLength: 100,
          pattern: "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
          description: "URL-safe unique tenant identifier"
        },
        status: {
          enum: ["provisioning", "active", "suspended", "deactivated", "failed"],
          description: "Tenant lifecycle status"
        },
        tier: {
          enum: ["free", "standard", "enterprise"],
          description: "Subscription tier"
        },
        contactEmail: {
          bsonType: "string",
          pattern: "^[^@]+@[^@]+\\.[^@]+$",
          description: "Primary contact email"
        },
        billingEmail: {
          bsonType: ["string", "null"],
          description: "Billing contact email"
        },
        metadata: {
          bsonType: "object",
          description: "Extensible metadata"
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
        deactivatedAt: {
          bsonType: ["date", "null"],
          description: "Deactivation timestamp"
        },
        createdBy: {
          bsonType: "string",
          description: "UUID of creating user/service"
        },
        // Embedded configuration for performance (denormalized)
        configuration: {
          bsonType: "object",
          description: "Tenant configuration as key-value pairs",
          properties: {
            features: {
              bsonType: "object",
              properties: {
                skillsFramework: { bsonType: "bool" },
                recommendations: { bsonType: "bool" },
                learningPaths: { bsonType: "bool" },
                analytics: { bsonType: "bool" }
              }
            },
            limits: {
              bsonType: "object",
              properties: {
                maxUsers: { bsonType: "int" },
                maxOrganizations: { bsonType: "int" },
                apiRateLimit: { bsonType: "int" }
              }
            },
            retention: {
              bsonType: "object",
              properties: {
                auditLogsDays: { bsonType: "int" },
                analyticsDays: { bsonType: "int" }
              }
            },
            privacy: {
              bsonType: "object",
              properties: {
                dataRegion: { bsonType: "string" },
                gdprEnabled: { bsonType: "bool" }
              }
            },
            branding: {
              bsonType: "object",
              properties: {
                logoUrl: { bsonType: ["string", "null"] },
                primaryColor: { bsonType: "string" }
              }
            },
            notifications: {
              bsonType: "object",
              properties: {
                emailEnabled: { bsonType: "bool" },
                webhookUrl: { bsonType: ["string", "null"] }
              }
            }
          }
        }
      }
    }
  }
});

// Indexes for tenants collection
db.tenants.createIndex({ "slug": 1 }, { unique: true, name: "idx_slug_unique" });
db.tenants.createIndex({ "status": 1 }, { name: "idx_status" });
db.tenants.createIndex({ "tier": 1 }, { name: "idx_tier" });
db.tenants.createIndex({ "createdAt": 1 }, { name: "idx_created_at" });
db.tenants.createIndex({ "status": 1, "createdAt": -1 }, { name: "idx_status_created" });
db.tenants.createIndex({ "contactEmail": 1 }, { name: "idx_contact_email" });

// Collection: idempotency_keys
db.createCollection("idempotency_keys", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "idempotencyKey", "operation", "requestHash", "status", "createdAt", "expiresAt"],
      properties: {
        _id: {
          bsonType: "string",
          description: "UUID key identifier"
        },
        tenantId: {
          bsonType: ["string", "null"],
          description: "Associated tenant ID (null for tenant creation)"
        },
        idempotencyKey: {
          bsonType: "string",
          description: "Client-provided idempotency key"
        },
        operation: {
          bsonType: "string",
          description: "Operation name (e.g., 'create_tenant')"
        },
        resourceId: {
          bsonType: ["string", "null"],
          description: "Created resource ID"
        },
        requestHash: {
          bsonType: "string",
          description: "SHA-256 hash of request body"
        },
        responseData: {
          bsonType: ["object", "null"],
          description: "Cached response data"
        },
        status: {
          enum: ["pending", "completed", "failed"],
          description: "Operation status"
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

// Indexes for idempotency_keys
db.idempotency_keys.createIndex({ "idempotencyKey": 1 }, { unique: true, name: "idx_key_unique" });
db.idempotency_keys.createIndex({ "expiresAt": 1 }, { expireAfterSeconds: 0, name: "idx_ttl_expire" });
db.idempotency_keys.createIndex({ "status": 1 }, { name: "idx_status" });
db.idempotency_keys.createIndex({ "tenantId": 1 }, { sparse: true, name: "idx_tenant_id" });

// Collection: tenant_audit_logs (time-series optimized)
db.createCollection("tenant_audit_logs", {
  timeseries: {
    timeField: "createdAt",
    metaField: "tenantId",
    granularity: "hours"
  },
  expireAfterSeconds: 31536000 // 365 days default retention
});

// Additional indexes for audit logs
db.tenant_audit_logs.createIndex({ "tenantId": 1, "createdAt": -1 }, { name: "idx_tenant_time" });
db.tenant_audit_logs.createIndex({ "action": 1 }, { name: "idx_action" });
db.tenant_audit_logs.createIndex({ "actorId": 1 }, { name: "idx_actor" });
db.tenant_audit_logs.createIndex({ "resourceType": 1, "resourceId": 1 }, { name: "idx_resource" });

// =============================================================================
// Default Configuration Template
// =============================================================================

const DEFAULT_TENANT_CONFIGURATION = {
  features: {
    skillsFramework: true,
    recommendations: true,
    learningPaths: true,
    analytics: true
  },
  limits: {
    maxUsers: 100,
    maxOrganizations: 10,
    apiRateLimit: 1000
  },
  retention: {
    auditLogsDays: 365,
    analyticsDays: 730
  },
  privacy: {
    dataRegion: "us-east-1",
    gdprEnabled: true
  },
  branding: {
    logoUrl: null,
    primaryColor: "#1a73e8"
  },
  notifications: {
    emailEnabled: true,
    webhookUrl: null
  }
};

// Tier-based configuration overrides
const TIER_CONFIGURATIONS = {
  free: {
    limits: {
      maxUsers: 10,
      maxOrganizations: 1,
      apiRateLimit: 100
    },
    features: {
      analytics: false
    }
  },
  standard: {
    // Uses defaults
  },
  enterprise: {
    limits: {
      maxUsers: -1, // unlimited
      maxOrganizations: -1, // unlimited
      apiRateLimit: 10000
    },
    retention: {
      auditLogsDays: 730,
      analyticsDays: 2555 // 7 years
    }
  }
};
