"""ASIWDP skills taxonomy persistence (PostgreSQL + MongoDB)."""

from asiwdp_skills_persistence.mongodb import (
    RoleMetaRepository,
    SkillMetaRepository,
    ensure_meta_collections,
)

__all__ = [
    "SkillMetaRepository",
    "RoleMetaRepository",
    "ensure_meta_collections",
]

__version__ = "0.1.0"
