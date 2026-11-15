"""Shared helpers: scenario files, throwaway project copies, configs that use only the scripted model."""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from codedoctor import config as config_mod

REPO = Path(__file__).resolve().parents[3]
SCENARIOS = REPO / "bench" / "scenarios"


class BenchError(RuntimeError):
    """The scenario did not set up what it says (e.g. a review that should refute a claim did not)."""


def load(suite: str, scenarios_dir: Path | None = None) -> list[dict]:
    base = (scenarios_dir or SCENARIOS) / suite
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(base.glob("*.json"))]


@contextmanager
def project_copy(scenario: dict) -> Iterator[tuple[Path, Path]]:
    """(project root, data dir) in a fresh temporary directory, removed afterwards. Scenarios may edit the copy."""
    tmp = Path(tempfile.mkdtemp(prefix="cd-bench-"))
    try:
        root = tmp / "project"
        shutil.copytree(REPO / scenario["project"], root)
        yield root, tmp / "data"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scripted_config(root: Path, data: Path, name: str, agents: list[dict],
                    embedding_from: config_mod.ProjectConfig | None = None, max_steps: int = 16,
                    computer: dict | None = None) -> config_mod.ProjectConfig:
    """Agents use only the scripted model. `embedding_from`: the user's own configuration, whose embedding
    endpoint and model (their choice) are copied in for semantic recall; nothing else is taken from it."""
    raw = {
        "cd_schema": "cd.config.project/0",
        "project": {"name": name, "root": str(root), "data_dir": str(data)},
        "endpoints": [{"id": "bench", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": agents,
        "defaults": {"budget": {"max_steps": max_steps}, "stall_steps": 4},
    }
    if computer is not None:  # computer use is on in every project (config.START_COMPUTER); a bench may measure without it
        raw["computer"] = computer
    if embedding_from is not None:
        emb = embedding_from.embedding
        ep = embedding_from.endpoints[emb.endpoint]
        if ep.id != "bench":
            raw["endpoints"].append({k: v for k, v in {
                "id": ep.id, "kind": ep.kind, "base_url": ep.base_url, "local": ep.local, "api_key_env": ep.api_key_env,
                "api_key_keyring": ep.api_key_keyring, "max_data_class": ep.max_data_class, "timeout_s": ep.timeout_s,
            }.items() if v is not None})
        raw["memory"] = {"embedding": {"endpoint": emb.endpoint, "model": emb.model, "min_similarity": emb.min_similarity}}
    return config_mod.parse(raw)


def short(entity: str) -> str:
    return entity.rsplit("#", 1)[-1] if "#" in entity else entity.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
