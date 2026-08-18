# ASIWDP Skills Framework Service

Version-aware RESTful APIs for skills, categories, and proficiency levels,
plus bulk CSV/JSON import and taxonomy export pipelines.

| Concern | Location |
|---------|----------|
| FastAPI app / routers | `src/asiwdp_skills_framework/` |
| Bulk import validation | `services/bulk_import.py` |
| Taxonomy export stream | `services/taxonomy_export.py` |
| JSON request schemas | `json_schemas/` |
| OpenAPI (canonical) | [`openapi/skills-framework-service.yaml`](../../openapi/skills-framework-service.yaml) |

## Install

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "libs/skills-persistence[dev]"
pip install -e "services/skills-framework[dev]"
```

## Run (local)

```bash
export ASIWDP_DATABASE_URL="${ASIWDP_DATABASE_URL:-}"  # optional; in-memory if unset
uvicorn asiwdp_skills_framework.app:create_app --factory --reload --port 8080
```

## Tests

```bash
pytest services/skills-framework/tests -q
```

## OpenAPI lint & portal publish

```bash
./scripts/validate_and_publish_openapi.sh
```
