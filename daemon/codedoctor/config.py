"""Project configuration (schemas/config/project.schema.json), loaded from JSON or TOML.

The configuration is the user's decision record: which endpoint and model every
agent uses, and which fallbacks (if any) it may use. Nothing in the daemon
changes these choices.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from codedoctor.protocol.registry import validator

SCHEMA = "config/project.schema.json"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Endpoint:
    id: str
    kind: str
    base_url: str
    local: bool
    api_key_env: str | None = None
    max_data_class: str = "internal"
    max_concurrency: int = 4
    timeout_s: float = 120.0
    api_key_keyring: bool = False
    name: str = ""
    provider: str = ""
    models: tuple[str, ...] = ()
    text_tool_calls: bool = True


@dataclass(frozen=True)
class ModelChoice:
    endpoint: str
    model: str


@dataclass(frozen=True)
class AgentConfig:
    id: str
    role: str
    primary: ModelChoice
    fallbacks: tuple[ModelChoice, ...] = ()
    temperature: float | None = None
    max_output_tokens: int | None = None
    reasoning: str | None = None  # 思考强度 (models/reasoning.py); None: the provider's default
    context_budget_tokens: int = 64000
    tools: tuple[str, ...] | None = None
    recall_k: int = 8
    shared_read: bool = True
    system_prompt_extra: str = ""
    supervises: str | None = None
    supervises_workers: tuple[str, ...] = ()  # small squad: one guardian re-checks two workers (ChatGPT's field name)
    team: bool = False  # a member of the Lumen team (agents/team.py); not part of the cluster modes

    @property
    def watched(self) -> tuple[str, ...]:
        """Every worker this guardian re-checks."""
        return ((self.supervises,) if self.supervises else ()) + tuple(w for w in self.supervises_workers if w != self.supervises)


@dataclass(frozen=True)
class EmbeddingConfig:
    """Semantic recall (ADR 0007). Present only when the user chose an embedding endpoint and model."""
    endpoint: str
    model: str
    min_similarity: float = 0.35


@dataclass(frozen=True)
class Permissions:
    run_command: str = "deny"
    command_allowlist: tuple[str, ...] = ()
    write_files: bool = False
    test_command: str = ""  # run by the system before and after every change (ADR 0016); "" = no automatic tests


@dataclass(frozen=True)
class ClusterPolicy:
    enabled: bool = False
    max_agents: int = 40      # heads, workers and guardians; single agents are not part of the cluster
    # basic: 单人助手 | dual: 双人互检 (one worker, one guardian, no heads) | small: 协作小队 (two heads, one guardian per
    # two workers) | advanced: 双首脑集群 (two heads, one guardian per worker) | collab: advanced, one subtask at a time
    mode: str = "advanced"
    parallel: bool = True     # advanced mode only: the dispatch head may run several pairs at once
    squad: bool = True        # changing code with heads: main pair + alternates in copies + scouts (ADR 0016 item 14)
    foresight: bool = False
    interval_s: float = 30.0
    max_steps_per_cycle: int = 8
    max_tokens_per_cycle: int = 20000
    reserved_tokens_per_hour: int = 1000000

    @property
    def parallel_subtasks(self) -> bool:
        return self.mode in ("advanced", "small") and self.parallel


@dataclass(frozen=True)
class LaunchTarget:
    id: str
    path: str
    args: tuple[str, ...] = ()
    cwd: str | None = None


@dataclass(frozen=True)
class ComputerPolicy:
    """Computer use (ADR 0012). Off unless the user turns each capability on."""
    screenshot: str = "off"   # off | on
    input: str = "off"        # off | guardian | ask
    apps: str = "off"
    terminal: str = "off"
    capture: str = "windows"  # windows | screen
    background: bool = True   # work in the window itself, not with the user's mouse and keyboard (computer/desktop.py)
    windows: tuple[str, ...] = ()
    launch: tuple[LaunchTarget, ...] = ()
    screenshot_data_class: str = "internal"
    guardian_timeout_s: int = 180
    user_timeout_s: int = 600
    max_actions_per_task: int = 200
    disabled: bool = False    # 设置 → 电脑操作权限 → 禁止电脑操作: the only way it is fully off

    @property
    def enabled(self) -> bool:
        return not self.disabled and self.screenshot != "off" or any(m != "off" for m in (self.input, self.apps, self.terminal))


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    root: Path
    data_dir: Path
    endpoints: dict[str, Endpoint]
    agents: dict[str, AgentConfig]
    permissions: Permissions = field(default_factory=Permissions)
    code_data_class: str = "internal"
    max_steps: int = 40
    max_tokens: int = 300_000
    stall_steps: int = 6
    source: Path | None = None
    embedding: EmbeddingConfig | None = None
    cluster: ClusterPolicy = field(default_factory=ClusterPolicy)
    computer: ComputerPolicy = field(default_factory=ComputerPolicy)


def load_raw(path: Path | str) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)


def load(path: Path | str) -> ProjectConfig:
    path = Path(path)
    return parse(load_raw(path), base_dir=path.parent, source=path)


def save_raw(raw: dict, path: Path | str) -> ProjectConfig:
    """Validate, then write the configuration (TOML or JSON by extension). Returns the parsed result.
    The previous file is kept as <name>.bak."""
    path = Path(path)
    cfg = parse(raw, base_dir=path.parent, source=path)  # raises ConfigError before anything is written
    text = dump_toml(raw) if path.suffix == ".toml" else json.dumps(raw, ensure_ascii=False, indent=2)
    if path.exists():
        path.with_suffix(path.suffix + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return cfg


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_toml_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(f"cannot write {type(v).__name__} to TOML")


def dump_toml(raw: dict) -> str:
    """Write the project configuration as readable TOML (tables, arrays of tables, inline tables for small dicts)."""
    lines = ["# Lumen project configuration. Every agent's model is your choice; keys are never stored here.", ""]
    scalars = {k: v for k, v in raw.items() if not isinstance(v, (dict, list))}
    for k, v in scalars.items():
        lines.append(f"{k} = {_toml_value(v)}")
    for k, v in raw.items():
        if isinstance(v, dict):
            lines += ["", f"[{k}]"] + [f"{kk} = {_toml_value(vv)}" for kk, vv in v.items()]
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            for item in v:
                lines += ["", f"[[{k}]]"] + [f"{kk} = {_toml_value(vv)}" for kk, vv in item.items()]
        elif isinstance(v, list):
            lines.append(f"{k} = {_toml_value(v)}")
    return "\n".join(lines) + "\n"


# What agents may run when the configuration says nothing, or still says "deny" (the user, 2026-11-13: the three approval choices
# decide what is asked; an old configuration works as it is and nobody is sent to edit it).
START_COMMANDS = ["python", "py", "pip", "pytest", "npm", "npx", "pnpm", "yarn", "node", "tsc", "git", "cargo", "go", "dotnet", "make",
                  "cmake", "mvn", "gradle", "dir", "ls", "cat", "type", "echo", "rm", "rmdir", "del"]


def normalize_raw(raw: dict) -> dict:
    """Make a raw configuration fit the schema before it is checked (it is given a COPY: the user's file and the page's own copy are
    never changed behind their back): an empty allowlist is filled, a "deny" becomes the allowlist. A schema message never reaches
    the user for what we can mend ourselves."""
    perm = raw.get("permissions")
    if isinstance(perm, dict) and perm.get("run_command", "allowlist") in ("deny", "allowlist"):
        perm["run_command"] = "allowlist"
        if not perm.get("command_allowlist"):
            perm["command_allowlist"] = list(START_COMMANDS)
    return raw


def parse(raw: dict, base_dir: Path | None = None, source: Path | None = None) -> ProjectConfig:
    import copy

    raw = normalize_raw(copy.deepcopy(raw))  # in memory only: what is on disk stays as the user wrote it until they save
    errors = list(validator(SCHEMA).iter_errors(raw))
    if errors:
        e = errors[0]
        where = "/" + "/".join(str(p) for p in e.absolute_path)
        # jsonschema puts the whole offending value into its message (a list of 41 agents...); say what is wrong instead
        short = {"maxItems": f"has more than {e.validator_value} items", "minItems": f"needs at least {e.validator_value} items",
                 "maxLength": f"is longer than {e.validator_value} characters", "minLength": "must not be empty",
                 "required": e.message, "additionalProperties": e.message, "enum": f"must be one of {e.validator_value}",
                 "type": f"must be of type {e.validator_value}"}.get(e.validator)
        message = short or (e.message if len(e.message) <= 300 else e.message[:300] + "...")
        raise ConfigError(f"config {where}: {message}")

    base_dir = base_dir or Path.cwd()
    proj = raw["project"]
    root = (base_dir / proj["root"]).resolve()
    data_dir = (
        (base_dir / proj["data_dir"]).resolve()
        if "data_dir" in proj
        # CODEDOCTOR_HOME too: a test run in a home of its own kept writing chats into the user's ~/.codedoctor (2026-11-14)
        else Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor") / "projects" / proj["name"]
    )

    endpoints: dict[str, Endpoint] = {}
    for e in raw["endpoints"]:
        if e["id"] in endpoints:
            raise ConfigError(f"duplicate endpoint id {e['id']!r}")
        endpoints[e["id"]] = Endpoint(
            id=e["id"],
            kind=e["kind"],
            base_url=e["base_url"].rstrip("/"),
            local=e["local"],
            api_key_env=e.get("api_key_env"),
            max_data_class=e.get("max_data_class", "local_only" if e["local"] else "internal"),
            max_concurrency=e.get("max_concurrency", 1 if e["local"] else 4),
            timeout_s=e.get("timeout_s", 300.0 if e["local"] else 120.0),
            api_key_keyring=e.get("api_key_keyring", False),
            name=e.get("name", e["id"]),
            provider=e.get("provider", ""),
            models=tuple(e.get("models", ())),
            text_tool_calls=e.get("text_tool_calls", True),
        )

    agents: dict[str, AgentConfig] = {}
    for a in raw["agents"]:
        if a["id"] in agents:
            raise ConfigError(f"duplicate agent id {a['id']!r}")
        choices = [ModelChoice(a["endpoint"], a["model"])] + [ModelChoice(f["endpoint"], f["model"]) for f in a.get("fallbacks", [])]
        for c in choices:
            if c.endpoint not in endpoints:
                raise ConfigError(f"agent {a['id']!r} uses unknown endpoint {c.endpoint!r}")
        params = a.get("params", {})
        mem = a.get("memory", {})
        agents[a["id"]] = AgentConfig(
            id=a["id"],
            role=a["role"],
            primary=choices[0],
            fallbacks=tuple(choices[1:]),
            temperature=params.get("temperature"),
            reasoning=params.get("reasoning"),
            max_output_tokens=params.get("max_output_tokens"),
            context_budget_tokens=a.get("context_budget_tokens", 64000),
            tools=tuple(a["tools"]) if "tools" in a else None,
            recall_k=mem.get("recall_k", 8),
            shared_read=mem.get("shared_read", True),
            system_prompt_extra=a.get("system_prompt_extra", ""),
            supervises=a.get("supervises"),
            supervises_workers=tuple(a.get("supervises_workers", ())),
            team=bool(a.get("team", False)),
        )

    for a in agents.values():
        for w in a.watched:
            if w not in agents or agents[w].role not in ("worker", "investigator"):
                raise ConfigError(f"guardian {a.id!r} supervises {w!r}, which is not a configured worker")
    embedding = None
    if emb := raw.get("memory", {}).get("embedding"):
        ep = endpoints.get(emb["endpoint"])
        if ep is None:
            raise ConfigError(f"memory.embedding uses unknown endpoint {emb['endpoint']!r}")
        if ep.kind not in ("openai_compatible", "scripted"):
            raise ConfigError(f"memory.embedding: endpoint {ep.id!r} is {ep.kind}, which has no embeddings API; "
                              "choose an OpenAI-compatible endpoint (e.g. Ollama, OpenAI, SiliconFlow)")
        embedding = EmbeddingConfig(emb["endpoint"], emb["model"], emb.get("min_similarity", 0.35))
    perm = raw.get("permissions", {})
    defaults = raw.get("defaults", {})
    budget = defaults.get("budget", {})
    cluster_raw = raw.get("cluster", {})
    foresight = cluster_raw.get("foresight", {})
    cluster = ClusterPolicy(
        enabled=cluster_raw.get("enabled", False), max_agents=cluster_raw.get("max_agents", 40),
        mode=cluster_raw.get("mode", "advanced"), parallel=cluster_raw.get("parallel", True),
        squad=cluster_raw.get("squad", True),
        foresight=foresight.get("enabled", False), interval_s=foresight.get("interval_s", 30),
        max_steps_per_cycle=foresight.get("max_steps_per_cycle", 8),
        max_tokens_per_cycle=foresight.get("max_tokens_per_cycle", 20000),
        reserved_tokens_per_hour=foresight.get("reserved_tokens_per_hour", 1000000))
    validate_cluster(agents, cluster)
    computer = parse_computer(raw["computer"] if "computer" in raw else START_COMPUTER)
    return ProjectConfig(
        name=proj["name"],
        root=root,
        data_dir=data_dir,
        endpoints=endpoints,
        agents=agents,
        permissions=Permissions(
            run_command="allowlist",  # every project is governed by the approval choice (批准方式): what an old file says about
            write_files=True,         # "deny" or "off" counts as on, in memory; saving from the settings writes what they set
            command_allowlist=tuple(perm.get("command_allowlist") or START_COMMANDS),
            test_command=perm.get("test_command", ""),
        ),
        code_data_class=proj.get("code_data_class", "internal"),
        max_steps=budget.get("max_steps", 40),
        max_tokens=budget.get("max_tokens", 300_000),
        stall_steps=defaults.get("stall_steps", 6),
        source=source,
        embedding=embedding,
        cluster=cluster,
        computer=computer,
    )


# What computer use is when the configuration says nothing (the user, 2026-11-13: usable from the start). The window list is one
# empty fragment, which matches every window; the supervisor still checks every action and the approval choice (批准方式)
# decides what the user is asked.
START_COMPUTER = {"screenshot": "on", "input": "guardian", "apps": "guardian", "terminal": "guardian", "windows": [""]}


def parse_computer(c: dict) -> ComputerPolicy:
    if c.get("disabled"):
        return ComputerPolicy(disabled=True)
    policy = ComputerPolicy(
        # no lists of windows or programs to fill in any more (the user, 2026-11-14: "把所有的白名单全都删掉"): with nothing
        # said every window is open (the empty fragment) and any program may be started; the 批准方式 decides who is asked
        screenshot=c.get("screenshot", "off"), input=c.get("input", "off"),
        apps=c.get("apps", "guardian" if c.get("input", "off") != "off" else "off"),
        terminal=c.get("terminal", "off"), capture=c.get("capture", "windows"), windows=tuple(c.get("windows") or ("",)),
        background=bool(c.get("background", True)),
        launch=tuple(LaunchTarget(t["id"], t["path"], tuple(t.get("args", ())), t.get("cwd")) for t in c.get("launch", ())),
        screenshot_data_class=c.get("screenshot_data_class", "internal"),
        guardian_timeout_s=c.get("guardian_timeout_s", 180), user_timeout_s=c.get("user_timeout_s", 600),
        max_actions_per_task=c.get("max_actions_per_task", 200))
    if policy.input != "off" and policy.screenshot == "off":
        raise ConfigError("computer.input needs computer.screenshot = \"on\": approvers must see what an action is aimed at")
    if len({t.id for t in policy.launch}) != len(policy.launch):
        raise ConfigError("computer.launch ids must be unique")
    return policy


CLUSTER_ROLES = {"head_dispatch", "head_logic", "worker", "investigator", "guardian"}
CLUSTER_MODES = ("basic", "dual", "small", "collab", "advanced")
MAX_PAIRS = 19  # 2 heads + 19 worker/guardian pairs = 40


def validate_cluster(agents, policy):
    agents = {k: a for k, a in agents.items() if not a.team}  # the Lumen team lives beside the cluster modes
    members = [a for a in agents.values() if a.role in CLUSTER_ROLES]
    if len(members) > policy.max_agents or len(members) > 40:
        raise ConfigError("cluster agent count (heads, workers and guardians) exceeds the user limit or hard ceiling of 40 "
                          f"(2 heads + {MAX_PAIRS} worker/guardian pairs)")
    if policy.mode not in CLUSTER_MODES:
        raise ConfigError(f"cluster.mode must be one of {', '.join(CLUSTER_MODES)}")
    if policy.mode in ("basic", "dual") and policy.enabled:
        raise ConfigError(f"cluster.mode '{policy.mode}' has no heads; it cannot be combined with cluster.enabled")
    if policy.foresight and not policy.enabled:
        raise ConfigError("continuous foresight requires cluster.enabled")
    workers = {a.id for a in agents.values() if a.role in {"worker", "investigator"}}
    guardians = [a for a in agents.values() if a.role == "guardian"]
    watched = [w for g in guardians for w in g.watched]
    if policy.mode == "dual":
        heads = [a for a in members if a.role in ("head_dispatch", "head_logic")]
        if heads or len(workers) != 1 or len(guardians) != 1 or watched != list(workers):
            raise ConfigError("双人互检 (dual) is exactly one worker and the one guardian that re-checks it, without heads")
        return
    if not policy.enabled:
        return
    for role in ("head_dispatch", "head_logic"):
        if sum(a.role == role for a in agents.values()) != 1:
            raise ConfigError("enabled cluster requires exactly one dispatch head and one logic head")
    if not workers or len(members) != 2 + len(workers) + len(guardians):
        raise ConfigError("enabled cluster consists only of two heads, workers and their guardians")
    if set(watched) != workers or len(watched) != len(workers):
        raise ConfigError("every worker requires exactly one guardian, and no worker may have two")
    per_guardian = 2 if policy.mode == "small" else 1
    if any(len(g.watched) != per_guardian for g in guardians):
        raise ConfigError("协作小队 (small): every guardian re-checks two workers" if policy.mode == "small"
                          else "双首脑集群: every guardian re-checks exactly one worker")
    if policy.reserved_tokens_per_hour < 2 * policy.max_tokens_per_cycle:
        raise ConfigError("foresight hourly reserve must cover a cycle for each head")


def independence_warnings(cfg: ProjectConfig) -> list[str]:
    """Guardians whose model is the same as the worker they re-check (ADR 0009). The same model tends to repeat the
    same mistake, so its re-check is weaker evidence. A warning only: the models stay the user's choice."""
    out = []
    same: dict[str, list[tuple[str, str]]] = {}  # model -> [(guardian, worker)]
    for a in cfg.agents.values():
        for wid in a.watched:
            w = cfg.agents.get(wid)
            if w and (a.primary.endpoint, a.primary.model) == (w.primary.endpoint, w.primary.model):
                same.setdefault(f"{w.primary.endpoint}/{w.primary.model}", []).append((a.id, w.id))
    # one sentence per model, however many pairs share it (19 identical lines are unreadable)
    for model, pairs in same.items():
        if len(pairs) == 1:
            g, w = pairs[0]
            out.append(f"监督者 {g} 和它监督的执行者 {w} 用的是同一个模型（{model}），复查时容易犯同样的错。"
                       "建议给监督者换一个不同的模型（不换也能运行）。")
        else:
            out.append(f"有 {len(pairs)} 对执行者和监督者用的是同一个模型（{model}）：{_pair_list([g for g, _ in pairs])}。"
                       "监督者和执行者用同一个模型，复查时容易犯同样的错。建议给这些监督者换一个不同的模型"
                       "（在“设置 → Agent 模型”里改；不换也能运行）。")
    return out


def _pair_list(guardians: list[str]) -> str:
    """'guardian-1 … guardian-19' -> '第 1–19 对'; other names are listed (at most 8)."""
    nums = sorted(int(g.split("-", 1)[1]) for g in guardians if g.startswith("guardian-") and g.split("-", 1)[1].isdigit())
    others = [g for g in guardians if not (g.startswith("guardian-") and g.split("-", 1)[1].isdigit())]
    runs, start = [], None
    for i, n in enumerate(nums):
        if start is None:
            start = n
        if i + 1 == len(nums) or nums[i + 1] != n + 1:
            runs.append(f"{start}" if start == n else f"{start}–{n}")
            start = None
    parts = ([f"第 {'、'.join(runs)} 对"] if runs else []) + others[:8] + ([f"等 {len(others)} 个"] if len(others) > 8 else [])
    return "，".join(parts)
