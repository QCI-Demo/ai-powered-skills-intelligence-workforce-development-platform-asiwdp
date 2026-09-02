"""Sanity checks for expected PostgreSQL schema constants."""

from asiwdp_skills_persistence.postgres import EXPECTED_INDEXES, EXPECTED_TABLES


def test_expected_tables_cover_story_entities():
    required = {
        "skill",
        "proficiency",
        "role",
        "competency_requirement",
        "audit_log",
    }
    assert required.issubset(set(EXPECTED_TABLES))


def test_expected_indexes_include_tenant_and_version():
    names = " ".join(EXPECTED_INDEXES)
    assert "tenant_id" in names
    assert "version" in names
    for table in ("skill", "proficiency", "role", "competency", "audit_log"):
        assert any(table in idx for idx in EXPECTED_INDEXES)
