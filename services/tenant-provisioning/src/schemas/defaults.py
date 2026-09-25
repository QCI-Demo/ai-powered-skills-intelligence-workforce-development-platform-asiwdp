"""Default configuration templates for new tenants."""

from __future__ import annotations

from typing import Any

# Default configurations applied during tenant provisioning.
# Keys follow dot-notation for hierarchical grouping.

DEFAULT_TENANT_CONFIGURATIONS: dict[str, Any] = {
    # Feature flags
    "features.skills_intelligence": True,
    "features.learning_paths": True,
    "features.recommendations": True,
    "features.analytics": True,
    "features.consent_management": True,
    "features.progress_tracking": True,
    # Tier-based limits (overridden by tier)
    "limits.max_users": 100,
    "limits.max_organizations": 10,
    "limits.max_skills": 5000,
    "limits.max_learning_paths": 500,
    "limits.max_competencies": 1000,
    "limits.storage_gb": 50,
    "limits.api_requests_per_minute": 1000,
    # Privacy and compliance
    "privacy.data_retention_days": 365,
    "privacy.gdpr_enabled": True,
    "privacy.ccpa_enabled": True,
    "privacy.consent_required": True,
    "privacy.audit_logging_enabled": True,
    # Integrations
    "integrations.sso_enabled": False,
    "integrations.scim_enabled": False,
    "integrations.webhook_enabled": False,
    "integrations.api_enabled": True,
    # Branding
    "branding.custom_logo_enabled": False,
    "branding.custom_domain_enabled": False,
    "branding.custom_theme_enabled": False,
    # Notifications
    "notifications.email_enabled": True,
    "notifications.in_app_enabled": True,
    "notifications.digest_frequency": "daily",
}

# Tier-specific overrides
TIER_CONFIGURATION_OVERRIDES: dict[str, dict[str, Any]] = {
    "free": {
        "limits.max_users": 10,
        "limits.max_organizations": 1,
        "limits.max_skills": 500,
        "limits.max_learning_paths": 50,
        "limits.storage_gb": 5,
        "limits.api_requests_per_minute": 100,
        "features.analytics": False,
        "integrations.api_enabled": False,
    },
    "standard": {
        # Uses defaults
    },
    "professional": {
        "limits.max_users": 500,
        "limits.max_organizations": 50,
        "limits.max_skills": 10000,
        "limits.max_learning_paths": 2000,
        "limits.storage_gb": 200,
        "limits.api_requests_per_minute": 5000,
        "integrations.sso_enabled": True,
        "integrations.webhook_enabled": True,
        "branding.custom_logo_enabled": True,
    },
    "enterprise": {
        "limits.max_users": -1,  # Unlimited
        "limits.max_organizations": -1,
        "limits.max_skills": -1,
        "limits.max_learning_paths": -1,
        "limits.storage_gb": -1,
        "limits.api_requests_per_minute": -1,
        "integrations.sso_enabled": True,
        "integrations.scim_enabled": True,
        "integrations.webhook_enabled": True,
        "branding.custom_logo_enabled": True,
        "branding.custom_domain_enabled": True,
        "branding.custom_theme_enabled": True,
    },
}


def get_default_configurations_for_tier(tier: str) -> dict[str, Any]:
    """Return merged default configurations for a given tier."""
    configs = DEFAULT_TENANT_CONFIGURATIONS.copy()
    overrides = TIER_CONFIGURATION_OVERRIDES.get(tier, {})
    configs.update(overrides)
    return configs
