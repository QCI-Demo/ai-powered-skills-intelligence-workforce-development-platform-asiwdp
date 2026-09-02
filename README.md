# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## MongoDB Flexible Attribute Collections

This branch delivers MongoDB `skill_meta` / `role_meta` collections with JSON
Schema validation for optional metadata and audit blobs, plus sample CRUD in
the data-access layer. Documents are tenant-scoped via `tenant_id` and
versioned via `version`.

| Artifact | Path |
|----------|------|
| Collection validators | [`db/mongodb/collections/`](db/mongodb/collections/) |
| Init script (create + indexes) | [`db/mongodb/init/create_collections.js`](db/mongodb/init/create_collections.js) |
| Data-access CRUD | [`libs/skills-persistence/`](libs/skills-persistence/) |

### Install & test

```bash
pip install -e "libs/skills-persistence[dev]"
pytest libs/skills-persistence/tests -q
```

### Create collections (mongosh)

```bash
mongosh "$MONGODB_URI" db/mongodb/init/create_collections.js
```
