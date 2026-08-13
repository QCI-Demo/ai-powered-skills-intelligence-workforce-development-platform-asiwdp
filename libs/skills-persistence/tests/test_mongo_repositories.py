"""CRUD coverage for skill_meta / role_meta repositories."""

from __future__ import annotations

import pytest

from asiwdp_skills_persistence.mongodb import (
    ROLE_META_COLLECTION,
    SKILL_META_COLLECTION,
    RoleMetaRepository,
    SkillMetaRepository,
    skill_meta_validator,
    role_meta_validator,
)

TENANT = "22222222-2222-2222-2222-222222222222"
SKILL = "b2000001-0000-4000-8000-000000000001"
ROLE = "c3000001-0000-4000-8000-000000000001"
OTHER_TENANT = "33333333-3333-3333-3333-333333333333"


def test_skill_meta_validator_requires_tenant_and_version():
    schema = skill_meta_validator()["$jsonSchema"]
    assert "tenant_id" in schema["required"]
    assert "version" in schema["required"]
    assert "skill_id" in schema["required"]


def test_role_meta_validator_requires_tenant_and_version():
    schema = role_meta_validator()["$jsonSchema"]
    assert "tenant_id" in schema["required"]
    assert "version" in schema["required"]
    assert "role_id" in schema["required"]


def test_ensure_collections_created(mongo_db):
    names = set(mongo_db.list_collection_names())
    assert SKILL_META_COLLECTION in names
    assert ROLE_META_COLLECTION in names


def test_skill_meta_crud_roundtrip(mongo_db):
    repo = SkillMetaRepository(mongo_db)

    created = repo.create(
        tenant_id=TENANT,
        skill_id=SKILL,
        version=1,
        metadata={"criticality": "high", "owner_team": "skills-platform"},
        tags=["core", "analytics"],
    )
    assert created["tenant_id"] == TENANT
    assert created["version"] == 1
    assert created["metadata"]["criticality"] == "high"

    fetched = repo.get(tenant_id=TENANT, skill_id=SKILL, version=1)
    assert fetched is not None
    assert fetched["tags"] == ["core", "analytics"]

    updated = repo.update_metadata(
        tenant_id=TENANT,
        skill_id=SKILL,
        version=1,
        metadata={"criticality": "medium"},
        tags=["core"],
    )
    assert updated is not None
    assert updated["metadata"]["criticality"] == "medium"
    assert updated["tags"] == ["core"]

    result = repo.append_audit_entry(
        tenant_id=TENANT,
        skill_id=SKILL,
        version=1,
        action="UPDATE",
        actor_id="11111111-1111-1111-1111-111111111111",
        detail={"field": "criticality"},
    )
    assert result.modified_count == 1
    after_audit = repo.get(tenant_id=TENANT, skill_id=SKILL, version=1)
    assert after_audit is not None
    assert len(after_audit["audit_entries"]) == 1
    assert after_audit["audit_entries"][0]["action"] == "UPDATE"

    listed = repo.list_for_tenant(tenant_id=TENANT, version=1)
    assert len(listed) == 1

    # Isolation: other tenant must not see the document
    assert repo.list_for_tenant(tenant_id=OTHER_TENANT) == []

    deleted = repo.delete(tenant_id=TENANT, skill_id=SKILL, version=1)
    assert deleted.deleted_count == 1
    assert repo.get(tenant_id=TENANT, skill_id=SKILL, version=1) is None


def test_role_meta_crud_roundtrip(mongo_db):
    repo = RoleMetaRepository(mongo_db)

    created = repo.create(
        tenant_id=TENANT,
        role_id=ROLE,
        version=1,
        metadata={"headcount_band": "IC3", "career_track": "individual"},
    )
    assert created["role_id"] == ROLE

    fetched = repo.get(tenant_id=TENANT, role_id=ROLE, version=1)
    assert fetched is not None
    assert fetched["metadata"]["career_track"] == "individual"

    updated = repo.update_metadata(
        tenant_id=TENANT,
        role_id=ROLE,
        version=1,
        metadata={"headcount_band": "IC4"},
    )
    assert updated is not None
    assert updated["metadata"]["headcount_band"] == "IC4"

    repo.append_audit_entry(
        tenant_id=TENANT,
        role_id=ROLE,
        version=1,
        action="PUBLISH",
        detail={"note": "initial publish"},
    )
    after = repo.get(tenant_id=TENANT, role_id=ROLE, version=1)
    assert after is not None
    assert after["audit_entries"][0]["action"] == "PUBLISH"

    assert len(repo.list_for_tenant(tenant_id=TENANT, version=1)) == 1
    assert repo.delete(tenant_id=TENANT, role_id=ROLE, version=1).deleted_count == 1


def test_invalid_version_rejected(mongo_db):
    repo = SkillMetaRepository(mongo_db)
    with pytest.raises(ValueError):
        repo.create(tenant_id=TENANT, skill_id=SKILL, version=0)
