"""Offline verification of exported receipt bytes; does not rerun scenarios."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    counts = []
    for case in document["cases"]:
        manifest = {entry["record"]["id"]: entry for entry in case["evidence_manifest"]}
        if len(manifest) != len(case["evidence_manifest"]):
            raise ValueError("duplicate manifest IDs")
        for entry in manifest.values():
            raw = entry["content_utf8"].encode("utf-8")
            content = entry["record"]["content"]
            if hashlib.sha256(raw).hexdigest() != content["sha256"] or len(raw) != content["size_bytes"]:
                raise ValueError("exported evidence content hash/size mismatch")
        receipts = case["status"]["evidence"]
        if len(receipts) != 24 or len(set(receipts)) != 24:
            raise ValueError("expected 24 independent execution receipts per demo case")
        for trial in case["trials"]:
            for record in trial["records"]:
                payload = json.loads(manifest[record["evidence"]]["content_utf8"])
                if payload != {key: value for key, value in record.items() if key != "evidence"}:
                    raise ValueError("receipt differs from original recorded bytes")
                harness = manifest[payload["harness_evidence"]]["record"]["content"]["sha256"]
                if harness != payload["harness"]:
                    raise ValueError("harness source differs from receipt")
        if any(eid not in manifest for eid in receipts):
            raise ValueError("missing receipt bytes")
        counts.append({"case": case["case"], "receipts": len(receipts), "manifest_items": len(manifest)})
    return {"verified": counts, "scope": "export_integrity_only_not_independent_reexecution"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    print(json.dumps(verify(parser.parse_args().report), indent=2))
