"""Validate JSON documents against a Code Doctor protocol schema.

    python -m tools.protocol.validate event/span.schema.json path/to/doc.json [...]

Exit code 0 if every document passes the schema and the semantic rules.
Fixture files (with "expect" and "instance") are unwrapped and their instance is checked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema.exceptions import best_match

from codedoctor.protocol import semantic
from codedoctor.protocol.registry import load_all, validator


def validate(schema: str, instance) -> list[str]:
    errors = list(validator(schema).iter_errors(instance))
    if errors:
        best = best_match(errors)
        where = "/" + "/".join(str(p) for p in best.absolute_path)
        return [f"schema: {where}: {best.message}"] + [f"  also: {e.message}" for e in errors if e is not best][:5]
    return [f"rule {v.rule}: {v.path}: {v.message}" for v in semantic.check(schema, instance)]


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in load_all():
        print(__doc__.strip())
        print("schemas:", ", ".join(sorted(load_all())))
        return 2
    schema, files = argv[0], argv[1:]
    failed = 0
    for f in files:
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        if isinstance(doc, dict) and {"expect", "instance"} <= doc.keys():
            doc = doc["instance"]
        problems = validate(schema, doc)
        print(f"{'FAIL' if problems else 'ok  '} {f}")
        for p in problems:
            print("     " + p)
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
