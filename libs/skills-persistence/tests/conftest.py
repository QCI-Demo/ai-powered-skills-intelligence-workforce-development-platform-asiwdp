"""Shared fixtures for skills-persistence tests."""

from __future__ import annotations

import mongomock
import pytest

from asiwdp_skills_persistence.mongodb import ensure_meta_collections


@pytest.fixture
def mongo_db():
    client = mongomock.MongoClient()
    db = client["asiwdp_skills_test"]
    ensure_meta_collections(db)
    return db
