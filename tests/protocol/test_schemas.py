"""Protocol v0 conformance tests.

Every fixture under schemas/*/fixtures/{valid,invalid}/ declares the schema it
targets and, for invalid fixtures, WHY it must fail (a JSON Schema keyword at a
path, or a semantic rule id). A fixture that fails for a different reason than
declared is a test failure: it means the rule we think protects us is not the
one doing the work.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from codedoctor.protocol import semantic
from codedoctor.protocol.registry import SCHEMA_ROOT, load_all, registry, validator

FIXTURES = sorted(SCHEMA_ROOT.glob("*/fixtures/*/*.json"))

# Schemas that describe whole documents and therefore need fixtures of both kinds.
DOCUMENT_SCHEMAS = {
    "event/span.schema.json",
    "event/action.schema.json",
    "event/coverage.schema.json",
    "event/telemetry-health.schema.json",
    "event/ws-correlation.schema.json",
    "event/chain-template.schema.json",
    "event/gap-assessment.schema.json",
    "evidence/evidence-record.schema.json",
    "evidence/evidence-ref.schema.json",
    "evidence/predicate.schema.json",
    "evidence/validation-result.schema.json",
    "claim/claim.schema.json",
    "agent/message.schema.json",
    "config/project.schema.json",
    "memory/note.schema.json",
    "memory/journal-entry.schema.json",
    "agent/side-effect.schema.json",
    "claim/status-event.schema.json",
    "event/coverage-status.schema.json",
    "graph/edge.schema.json",
    "graph/risk.schema.json",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(errors) -> list[ValidationError]:
    """All errors including those nested under anyOf/oneOf/if-then contexts."""
    out = []
    stack = list(errors)
    while stack:
        e = stack.pop()
        out.append(e)
        stack.extend(e.context or [])
    return out


def _path(e: ValidationError) -> str:
    return "/" + "/".join(str(p) for p in e.absolute_path)


# --- the schemas themselves ---------------------------------------------------

@pytest.mark.parametrize("name", sorted(load_all()))
def test_schema_is_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(load_all()[name])


def _refs(node):
    if isinstance(node, dict):
        if isinstance(node.get("$ref"), str):
            yield node["$ref"]
        for v in node.values():
            yield from _refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _refs(v)


@pytest.mark.parametrize("name", sorted(load_all()))
def test_every_ref_resolves(name):
    doc = load_all()[name]
    resolver = registry().resolver(base_uri=doc["$id"])
    for ref in _refs(doc):
        resolver.lookup(ref)  # raises if unresolvable


@pytest.mark.parametrize("name", sorted(DOCUMENT_SCHEMAS))
def test_document_schema_has_valid_and_invalid_fixtures(name):
    kinds = {_load(f)["expect"] for f in FIXTURES if _load(f)["schema"] == name}
    assert kinds == {"valid", "invalid"}, f"{name} needs both valid and invalid fixtures, has {kinds}"


@pytest.mark.parametrize("name", sorted(DOCUMENT_SCHEMAS))
def test_document_schema_declares_cd_schema_or_is_embedded(name):
    """Top-level records carry a cd_schema version tag; embedded fragments (ref, predicate) do not."""
    doc = load_all()[name]
    embedded = {"evidence/evidence-ref.schema.json", "evidence/predicate.schema.json"}
    has_tag = "cd_schema" in doc.get("properties", {})
    assert has_tag != (name in embedded)


# --- fixtures -----------------------------------------------------------------

@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: f"{p.parent.parent.parent.name}/{p.parent.name}/{p.stem}")
def test_fixture(path: Path):
    fx = _load(path)
    assert fx["expect"] == path.parent.name, "fixture 'expect' must match its folder"
    name, instance = fx["schema"], fx["instance"]
    errors = _flatten(validator(name).iter_errors(instance))
    top_level = list(validator(name).iter_errors(instance))

    if fx["expect"] == "valid":
        assert not top_level, "\n".join(f"{_path(e)}: {e.message}" for e in top_level)
        assert semantic.check(name, instance) == []
        return

    if "expect_rule" in fx:
        assert not top_level, f"expected only rule {fx['expect_rule']} to fail, but schema fails: {top_level[0].message}"
        rules = {v.rule for v in semantic.check(name, instance)}
        assert fx["expect_rule"] in rules, f"expected rule {fx['expect_rule']}, got {rules or 'none'}"
        return

    exp = fx["expect_error"]
    assert top_level, "fixture is expected to be invalid but passes the schema"

    def matches(e: ValidationError) -> bool:
        return (
            e.validator == exp["validator"]
            and _path(e).startswith(exp.get("path", "/"))
            and exp.get("message_contains", "") in e.message
        )

    assert any(matches(e) for e in errors), (
        f"no error matched {exp}; got:\n" + "\n".join(f"  {e.validator} at {_path(e)}: {e.message[:160]}" for e in errors)
    )


# --- targeted checks that are clearer as code than as fixtures -------------------

EV = "evidence/evidence-id.schema.json"
COMMIT = "9fceb02d0ae598e95dc970b74767f19372d61af8"
H = "a" * 64


@pytest.mark.parametrize("ev_id", [
    "ev:span:4bf92f3577b34da6a3ce929d0e0e4736/00f067aa0ba902b7",
    "ev:trace:4bf92f3577b34da6a3ce929d0e0e4736",
    f"ev:code:{COMMIT}:server/shop.py#ShopService.buy@{H}:L42-L61",
    f"ev:code:{COMMIT}:server/shop.py@{H}",
    f"ev:code:wt-{H}:web/src/Shop.tsx#ShopItemCard@{H}:L10",
    f"ev:log:{H}:L2210",
    "ev:test:01JB8Z9000000000000000TR01/tests%2Ftest_shop.py%3A%3Atest_buy",
    f"ev:blob:{H}",
    "ev:gap:01JB8Z6000000000000000GP01",
])
def test_evidence_id_accepts(ev_id):
    assert not list(validator(EV).iter_errors(ev_id))


@pytest.mark.parametrize("ev_id", [
    "ev:span:4bf92f3577b34da6a3ce929d0e0e4736",                     # missing span id
    "ev:span:00000000000000000000000000000000/00f067aa0ba902b7",    # zero trace id
    f"ev:code:main:server/shop.py@{H}",                              # branch name is not a version
    f"ev:code:{COMMIT}:C:/src/shop.py@{H}",                          # drive letter / absolute path
    f"ev:code:{COMMIT}:server/shop.py#ShopService.buy:L42",          # no content hash
    f"ev:code:{COMMIT}:server/shop.py@{H}:L0",                       # line numbers start at 1
    f"ev:log:{H}",                                                   # log needs a line
    "ev:gap:01JB8Z6000000000000000GPIL",                             # I and L are not Crockford base32
    "ev:hunch:anything",                                             # unknown kind
])
def test_evidence_id_rejects(ev_id):
    assert list(validator(EV).iter_errors(ev_id))


def _attrs_ok(attrs: dict) -> bool:
    schema = {"$ref": "https://code-doctor.local/schemas/v0/common/defs.schema.json#/$defs/attributes"}
    return not list(Draft202012Validator(schema, registry=registry()).iter_errors(attrs))


@pytest.mark.parametrize("key", [
    "gen_ai.usage.input_tokens", "llm.max_tokens", "session.id", "http.request.method",
    "user.id", "cd.tokenizer.name", "game.secretary_npc",
])
def test_non_sensitive_keys_keep_raw_values(key):
    assert _attrs_ok({key: "raw-value"})


@pytest.mark.parametrize("key", [
    "http.request.header.authorization", "http.request.header.cookie", "http.response.header.set-cookie",
    "user.password", "db.passwd", "access_token", "oauth.refresh_token", "http.request.header.x-api-key",
    "app.apikey", "client_secret", "aws.secrets", "ssh.private_key", "session_id", "credentials",
])
def test_sensitive_keys_require_redaction(key):
    assert not _attrs_ok({key: "raw-value"})
    assert _attrs_ok({key: "cd:redacted"})
    assert _attrs_ok({key: "cd:redacted:hmac:" + "0" * 64})
