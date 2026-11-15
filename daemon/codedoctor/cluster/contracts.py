"""Small deterministic business oracle. Unknown data is NOT a broken invariant."""
from __future__ import annotations

import json


class BusinessError(ValueError):
    pass


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_contract(contract: dict) -> None:
    if not isinstance(contract, dict) or set(contract) != {"id", "description", "rule"} or not isinstance(contract["id"], str) or not contract["id"] or not isinstance(contract["description"], str) or not contract["description"]:
        raise BusinessError("contract requires id, description and a bounded rule")
    rule = contract["rule"]
    if not isinstance(rule, dict) or rule.get("op") not in {"equal", "sum_equal", "unique"}:
        raise BusinessError("only equal, sum_equal and unique business rules are supported")
    fields = {"unique": {"op", "metric"}, "equal": {"op", "left", "right"}, "sum_equal": {"op", "parts", "total"}}
    if set(rule) != fields[rule["op"]]:
        raise BusinessError("unexpected or missing business rule fields")
    if rule["op"] == "sum_equal" and (not isinstance(rule["parts"], list) or not rule["parts"] or any(not isinstance(n, str) for n in rule["parts"]) or len(set(rule["parts"])) != len(rule["parts"])):
        raise BusinessError("sum_equal requires a nonempty distinct list of metric names")
    names = [rule["metric"]] if rule["op"] == "unique" else ([rule["left"], rule["right"]] if rule["op"] == "equal" else [*rule["parts"], rule["total"]])
    if not names or len(names) > 32 or any(not isinstance(n, str) or not n or len(n) > 128 for n in names):
        raise BusinessError("rules reference explicit metric names, never executable expressions")


def evaluate(contract: dict, metrics: dict) -> dict:
    validate_contract(contract)
    rule = contract["rule"]
    try:
        if rule["op"] == "unique":
            values = metrics[rule["metric"]]
            if not isinstance(values, list) or len(values) > 10000 or any(type(v) not in (str, int) for v in values):
                raise ValueError("unique needs a bounded list of logical ids")
            passed = len(values) == len(set(values))
        else:
            names = [rule["left"], rule["right"]] if rule["op"] == "equal" else [*rule["parts"], rule["total"]]
            values = [metrics[name] for name in names]
            # Money/state counters are integers in declared smallest units, not floats or booleans.
            if any(type(v) is not int or abs(v) > 10**18 for v in values):
                raise ValueError("numeric business metrics must be bounded integers")
            passed = values[0] == values[1] if rule["op"] == "equal" else sum(values[:-1]) == values[-1]
        return {"contract": contract["id"], "status": "holds" if passed else "violated"}
    except (KeyError, TypeError, ValueError):
        return {"contract": contract["id"], "status": "unknown"}
