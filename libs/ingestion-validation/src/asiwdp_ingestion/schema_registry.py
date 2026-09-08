"""Load and cache JSON Schema contracts from the contracts/ingestion tree."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from asiwdp_ingestion.errors import ContractNotFoundError, SchemaLoadError

# Canonical contract ids for workforce & learning-data ingestion.
DEFAULT_CONTRACTS: Mapping[str, str] = {
    "employee": "employee.schema.json",
    "role": "role.schema.json",
    "learning-content": "learning-content.schema.json",
    "learner-activity": "learner-activity.schema.json",
}

SCHEMA_VERSION = "1.0.0"
DEFAULT_MAJOR = "v1"


def _repo_contracts_root() -> Path | None:
    """Best-effort discovery of ``contracts/ingestion`` from CWD / package location."""
    candidates = [
        Path.cwd() / "contracts" / "ingestion",
        Path(__file__).resolve().parents[4] / "contracts" / "ingestion",
        Path(__file__).resolve().parents[3] / "contracts" / "ingestion",
    ]
    env = os.environ.get("ASIWDP_INGESTION_CONTRACTS_PATH")
    if env:
        candidates.insert(0, Path(env))
    for path in candidates:
        if path.is_dir() and (path / DEFAULT_MAJOR).is_dir():
            return path.resolve()
    return None


class SchemaRegistry:
    """Loads JSON schemas from the ingestion contract directory and compiles validators."""

    def __init__(
        self,
        contracts_root: str | Path,
        *,
        major: str = DEFAULT_MAJOR,
        schema_version: str = SCHEMA_VERSION,
        contract_map: Mapping[str, str] | None = None,
    ) -> None:
        self.contracts_root = Path(contracts_root).resolve()
        self.major = major
        self.schema_version = schema_version
        self.contract_map = dict(contract_map or DEFAULT_CONTRACTS)
        self._version_dir = self.contracts_root / self.major
        if not self._version_dir.is_dir():
            raise SchemaLoadError(
                f"Contract version directory not found: {self._version_dir}"
            )
        self._registry = self._build_registry()
        self._validators: dict[str, Draft202012Validator] = {}
        for contract_id in self.contract_map:
            self._validators[contract_id] = self._compile(contract_id)

    @classmethod
    def from_contracts_root(
        cls,
        contracts_root: str | Path | None = None,
        **kwargs: Any,
    ) -> SchemaRegistry:
        root = Path(contracts_root) if contracts_root else _repo_contracts_root()
        if root is None:
            raise SchemaLoadError(
                "Unable to locate contracts/ingestion. Pass contracts_root or set "
                "ASIWDP_INGESTION_CONTRACTS_PATH."
            )
        return cls(root, **kwargs)

    @property
    def contract_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.contract_map))

    def get_validator(self, contract_id: str) -> Draft202012Validator:
        try:
            return self._validators[contract_id]
        except KeyError as exc:
            raise ContractNotFoundError(
                f"Unknown ingestion contract '{contract_id}'. "
                f"Known: {', '.join(self.contract_ids)}"
            ) from exc

    def schema_document(self, contract_id: str) -> dict[str, Any]:
        filename = self.contract_map.get(contract_id)
        if filename is None:
            raise ContractNotFoundError(f"Unknown ingestion contract '{contract_id}'")
        return self._load_json(self._version_dir / filename)

    def _build_registry(self) -> Registry:
        resources: list[tuple[str, Resource]] = []
        for path in sorted(self._version_dir.glob("*.schema.json")):
            doc = self._load_json(path)
            # Register by filename so relative $ref (defs.schema.json#/...) resolve.
            resources.append((path.name, Resource.from_contents(doc, DRAFT202012)))
            schema_id = doc.get("$id")
            if isinstance(schema_id, str):
                resources.append((schema_id, Resource.from_contents(doc, DRAFT202012)))
        registry: Registry = Registry()
        for uri, resource in resources:
            registry = registry.with_resource(uri, resource)
        return registry

    def _compile(self, contract_id: str) -> Draft202012Validator:
        try:
            schema = self.schema_document(contract_id)
            return Draft202012Validator(
                schema,
                registry=self._registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )
        except ContractNotFoundError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as SchemaLoadError
            raise SchemaLoadError(
                f"Failed to compile schema for contract '{contract_id}': {exc}"
            ) from exc

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError as exc:
            raise SchemaLoadError(f"Schema file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise SchemaLoadError(f"Invalid JSON in schema file {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SchemaLoadError(f"Schema root must be an object: {path}")
        return data
