"""Default configuration seed for newly provisioned tenants."""

from __future__ import annotations

from typing import Any


DEFAULT_LOCALE = "en-US"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_REGION = "us-east-1"
DEFAULT_PLAN = "standard"


def build_default_configuration(
    *,
    timezone: str = DEFAULT_TIMEZONE,
    region: str = DEFAULT_REGION,
) -> dict[str, Any]:
    """Return the canonical default configuration map for a new tenant."""
    return {
        "locale": DEFAULT_LOCALE,
        "timezone": timezone or DEFAULT_TIMEZONE,
        "features.skills_framework": True,
        "features.recommendations": True,
        "features.learning_paths": True,
        "privacy.consent_required": True,
        "privacy.data_residency": region or DEFAULT_REGION,
        "rbac.default_learner_role": "learner",
        "metering.usage_events_enabled": True,
    }


def default_config_keys(
    *,
    timezone: str = DEFAULT_TIMEZONE,
    region: str = DEFAULT_REGION,
) -> list[str]:
    return list(build_default_configuration(timezone=timezone, region=region).keys())
