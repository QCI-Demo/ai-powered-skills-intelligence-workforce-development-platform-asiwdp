"""MongoDB flexible-attribute collections for skill/role metadata."""

from asiwdp_skills_persistence.mongodb.collections import (
    ROLE_META_COLLECTION,
    SKILL_META_COLLECTION,
    ensure_meta_collections,
    role_meta_validator,
    skill_meta_validator,
)
from asiwdp_skills_persistence.mongodb.repositories import (
    RoleMetaRepository,
    SkillMetaRepository,
)

__all__ = [
    "SKILL_META_COLLECTION",
    "ROLE_META_COLLECTION",
    "skill_meta_validator",
    "role_meta_validator",
    "ensure_meta_collections",
    "SkillMetaRepository",
    "RoleMetaRepository",
]
