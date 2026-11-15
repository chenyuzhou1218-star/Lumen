"""Load every schema under schemas/ into one referencing.Registry and build validators.

Schemas reference each other by relative $ref; each file's $id is
https://code-doctor.local/schemas/v0/<relative path>, so relative refs resolve
inside the registry without touching the network.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = REPO_ROOT / "schemas"
ID_BASE = "https://code-doctor.local/schemas/v0/"


def schema_files() -> list[Path]:
    return sorted(p for p in SCHEMA_ROOT.rglob("*.schema.json"))


def schema_name(path: Path) -> str:
    """'event/span.schema.json' style name, used by fixtures and the CLI."""
    return path.relative_to(SCHEMA_ROOT).as_posix()


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict]:
    schemas: dict[str, dict] = {}
    for path in schema_files():
        doc = json.loads(path.read_text(encoding="utf-8"))
        name = schema_name(path)
        expected_id = ID_BASE + name
        if doc.get("$id") != expected_id:
            raise ValueError(f"{name}: $id must be {expected_id!r}, got {doc.get('$id')!r}")
        schemas[name] = doc
    return schemas


@lru_cache(maxsize=1)
def registry() -> Registry:
    resources = [
        (doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012))
        for doc in load_all().values()
    ]
    return Registry().with_resources(resources)


def validator(name: str) -> Draft202012Validator:
    schema = load_all()[name]
    return Draft202012Validator(schema, registry=registry(), format_checker=FormatChecker())


def validator_for(uri: str) -> Draft202012Validator:
    """Validator for a sub-schema, e.g. '<schema $id>#/$defs/review'."""
    return Draft202012Validator({"$ref": uri}, registry=registry(), format_checker=FormatChecker())
