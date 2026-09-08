"""Consent-aware personal skill data ingestion for ASIWDP."""

from asiwdp_personal_data.consent_service import ConsentService, InMemoryConsentStore
from asiwdp_personal_data.errors import ConsentMissingError, PersonalDataError
from asiwdp_personal_data.ingestion import (
    InMemoryPersonalSkillStore,
    PersonalSkillDataIngestionPipeline,
    PersonalSkillStore,
)
from asiwdp_personal_data.models import (
    PERSONAL_SKILL_DATA_PURPOSE,
    ConsentRecord,
    ConsentStatus,
    PersonalSkillRecord,
)

__all__ = [
    "PERSONAL_SKILL_DATA_PURPOSE",
    "ConsentMissingError",
    "ConsentRecord",
    "ConsentService",
    "ConsentStatus",
    "InMemoryConsentStore",
    "InMemoryPersonalSkillStore",
    "PersonalDataError",
    "PersonalSkillDataIngestionPipeline",
    "PersonalSkillRecord",
    "PersonalSkillStore",
]

__version__ = "0.1.0"
