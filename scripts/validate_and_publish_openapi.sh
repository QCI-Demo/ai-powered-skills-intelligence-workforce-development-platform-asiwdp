#!/usr/bin/env bash
# Validate ASIWDP OpenAPI specs with openapi-spec-validator and publish the
# skills-framework service document to the local API portal staging directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="${ROOT}/openapi/skills-framework-service.yaml"
PORTAL_DIR="${ROOT}/openapi/portal"
PORTAL_STAMP="${PORTAL_DIR}/.published"

echo "==> Validating OpenAPI specs"
python3 - "$ROOT" <<'PY'
import sys
from pathlib import Path
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename

root = Path(sys.argv[1])
specs = sorted((root / "openapi").glob("*.yaml"))
if not specs:
    print("No OpenAPI YAML files found under openapi/", file=sys.stderr)
    sys.exit(1)

failed = 0
for spec in specs:
    try:
        spec_dict, _ = read_from_filename(str(spec))
        validate(spec_dict)
        print(f"OK  {spec.relative_to(root)}")
    except Exception as exc:  # noqa: BLE001
        failed += 1
        print(f"FAIL {spec.relative_to(root)}: {exc}", file=sys.stderr)

if failed:
    sys.exit(1)
print(f"Validated {len(specs)} specification(s)")
PY

echo "==> Publishing skills-framework-service.yaml to API portal staging"
mkdir -p "${PORTAL_DIR}"
cp -f "${SPEC}" "${PORTAL_DIR}/skills-framework-service.yaml"
cat > "${PORTAL_DIR}/README.md" <<EOF
# ASIWDP API Portal (staging)

Published OpenAPI documents for consumption by the developer portal.

| Spec | Source |
|------|--------|
| \`skills-framework-service.yaml\` | \`../skills-framework-service.yaml\` |

Last published: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
date -u +"%Y-%m-%dT%H:%M:%SZ" > "${PORTAL_STAMP}"
echo "Published to ${PORTAL_DIR}/skills-framework-service.yaml"
