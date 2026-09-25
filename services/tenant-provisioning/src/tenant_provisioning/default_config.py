"""Default tenant configuration factory."""

from __future__ import annotations

from typing import Any

from tenant_provisioning.models import ConfigCategory, PlanTier


def get_default_configurations(plan_tier: PlanTier) -> list[dict[str, Any]]:
    """Return default configuration entries based on plan tier.

    Each entry contains:
        - config_key: str
        - config_value: Any (will be stored as JSONB)
        - category: ConfigCategory
    """
    # Base configurations for all tiers
    base_configs = [
        # General settings
        {
            "config_key": "timezone",
            "config_value": "UTC",
            "category": ConfigCategory.GENERAL,
        },
        {
            "config_key": "locale",
            "config_value": "en-US",
            "category": ConfigCategory.GENERAL,
        },
        {
            "config_key": "date_format",
            "config_value": "YYYY-MM-DD",
            "category": ConfigCategory.GENERAL,
        },
        # Security settings
        {
            "config_key": "session_timeout_minutes",
            "config_value": 60,
            "category": ConfigCategory.SECURITY,
        },
        {
            "config_key": "mfa_required",
            "config_value": False,
            "category": ConfigCategory.SECURITY,
        },
        {
            "config_key": "password_policy",
            "config_value": {
                "min_length": 8,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_number": True,
                "require_special": False,
            },
            "category": ConfigCategory.SECURITY,
        },
        {
            "config_key": "allowed_ip_ranges",
            "config_value": [],
            "category": ConfigCategory.SECURITY,
        },
        # Feature flags
        {
            "config_key": "skills_ai_enabled",
            "config_value": True,
            "category": ConfigCategory.FEATURE_FLAGS,
        },
        {
            "config_key": "learning_paths_enabled",
            "config_value": True,
            "category": ConfigCategory.FEATURE_FLAGS,
        },
        {
            "config_key": "analytics_dashboard_enabled",
            "config_value": True,
            "category": ConfigCategory.FEATURE_FLAGS,
        },
        # Compliance settings
        {
            "config_key": "data_retention_days",
            "config_value": 365,
            "category": ConfigCategory.COMPLIANCE,
        },
        {
            "config_key": "gdpr_enabled",
            "config_value": True,
            "category": ConfigCategory.COMPLIANCE,
        },
        {
            "config_key": "audit_logging_enabled",
            "config_value": True,
            "category": ConfigCategory.COMPLIANCE,
        },
        # Notification settings
        {
            "config_key": "email_notifications_enabled",
            "config_value": True,
            "category": ConfigCategory.NOTIFICATIONS,
        },
        {
            "config_key": "webhook_url",
            "config_value": None,
            "category": ConfigCategory.NOTIFICATIONS,
        },
    ]

    # Tier-specific limits
    tier_limits: dict[PlanTier, dict[str, Any]] = {
        PlanTier.FREE: {
            "max_users": 5,
            "max_organizations": 1,
            "api_access_enabled": False,
            "custom_branding_enabled": False,
            "sso_enabled": False,
            "advanced_analytics_enabled": False,
        },
        PlanTier.STARTER: {
            "max_users": 50,
            "max_organizations": 3,
            "api_access_enabled": False,
            "custom_branding_enabled": False,
            "sso_enabled": False,
            "advanced_analytics_enabled": False,
        },
        PlanTier.PROFESSIONAL: {
            "max_users": 500,
            "max_organizations": 10,
            "api_access_enabled": True,
            "custom_branding_enabled": True,
            "sso_enabled": False,
            "advanced_analytics_enabled": True,
        },
        PlanTier.ENTERPRISE: {
            "max_users": -1,  # Unlimited
            "max_organizations": -1,
            "api_access_enabled": True,
            "custom_branding_enabled": True,
            "sso_enabled": True,
            "advanced_analytics_enabled": True,
        },
        PlanTier.CUSTOM: {
            "max_users": -1,
            "max_organizations": -1,
            "api_access_enabled": True,
            "custom_branding_enabled": True,
            "sso_enabled": True,
            "advanced_analytics_enabled": True,
        },
    }

    limits = tier_limits.get(plan_tier, tier_limits[PlanTier.STARTER])

    # Add tier-specific configurations
    tier_configs = [
        {
            "config_key": "max_users",
            "config_value": limits["max_users"],
            "category": ConfigCategory.GENERAL,
        },
        {
            "config_key": "max_organizations",
            "config_value": limits["max_organizations"],
            "category": ConfigCategory.GENERAL,
        },
        {
            "config_key": "api_access_enabled",
            "config_value": limits["api_access_enabled"],
            "category": ConfigCategory.FEATURE_FLAGS,
        },
        {
            "config_key": "custom_branding_enabled",
            "config_value": limits["custom_branding_enabled"],
            "category": ConfigCategory.FEATURE_FLAGS,
        },
        {
            "config_key": "sso_enabled",
            "config_value": limits["sso_enabled"],
            "category": ConfigCategory.SECURITY,
        },
        {
            "config_key": "advanced_analytics_enabled",
            "config_value": limits["advanced_analytics_enabled"],
            "category": ConfigCategory.FEATURE_FLAGS,
        },
    ]

    return base_configs + tier_configs
