# MongoDB Flexible Attribute Collections

| Collection | Purpose |
|------------|---------|
| `skill_meta` | Optional metadata + audit blobs for skills |
| `role_meta` | Optional metadata + audit blobs for roles |

Validators live in `collections/*.validator.json`. Initialization script:
`init/create_collections.js`.

Python CRUD: `libs/skills-persistence` → `SkillMetaRepository` /
`RoleMetaRepository`.
