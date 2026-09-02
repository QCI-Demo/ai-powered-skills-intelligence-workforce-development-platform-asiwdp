# asiwdp-skills-persistence

Data-access layer for the ASIWDP Skills Framework persistent domain model.

| Concern | Location |
|---------|----------|
| PostgreSQL DDL / Flyway | [`db/postgres/sql`](../../db/postgres/sql) |
| MongoDB validators | [`db/mongodb`](../../db/mongodb) |
| MongoDB CRUD repositories | `asiwdp_skills_persistence.mongodb` |

## Install

```bash
pip install -e "libs/skills-persistence[dev]"
```

## MongoDB usage sketch

```python
from pymongo import MongoClient
from asiwdp_skills_persistence.mongodb import (
    ensure_meta_collections,
    SkillMetaRepository,
)

client = MongoClient(os.environ["MONGODB_URI"])
db = client["asiwdp_skills"]
ensure_meta_collections(db)

repo = SkillMetaRepository(db)
repo.create(
    tenant_id="22222222-2222-2222-2222-222222222222",
    skill_id="b2000001-0000-4000-8000-000000000001",
    version=1,
    metadata={"source_system": "hris", "criticality": "high"},
)
```

## Tests

```bash
pytest libs/skills-persistence/tests -q
```
