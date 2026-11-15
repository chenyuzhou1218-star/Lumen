"""Command line. Inside a project's code folder no --config is needed: the project the window registered for that
folder is used (else --project NAME, else the most recently opened one).

  codedoctor fix     "what is wrong"              the whole team as configured, live progress, then the result
  codedoctor tasks                                recent investigations
  codedoctor show    [TASK|last] [--json]         result: answer, team, changes, tests, scout findings
  codedoctor undo    [TASK|last] [--yes]          put back the files an investigation changed
  codedoctor projects                             the projects the window knows
  codedoctor gui     --config cd.toml            desktop window (service runs inside it)
  codedoctor serve   [--host 127.0.0.1] [--port 8765] [--token T]   HTTP API (docs/api.md)
  codedoctor run     --config cd.toml --agent doctor [--title T] "instructions"
  codedoctor check   --config cd.toml            validate config, reach every endpoint
  codedoctor memory  --config cd.toml --reader doctor "query"
  codedoctor journal --config cd.toml --task task_...
  codedoctor coverage --config cd.toml           observation coverage list
  codedoctor bench   [--suite memory|reasoning|context] [--out bench/results]   scored memory / reasoning scenarios
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from codedoctor import config as config_mod


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


async def _run(cfg, agent: str, title: str, instructions: str, timeout: float) -> int:
    from codedoctor.agents.daemon import Daemon

    d = Daemon(cfg, poll_s=0.5)
    await d.start()
    try:
        sub = d.submit_task(agent, title, instructions)
        print(f"task {sub['task_id']} -> {agent} ({cfg.agents[agent].primary.endpoint}/{cfg.agents[agent].primary.model})", file=sys.stderr)
        report = await d.wait_for_report(sub["task_id"], timeout)
        for m in d.s.bus.list(task_id=sub["task_id"]):
            if m["kind"] == "escalation":
                print(f"[escalation] {m['body']['reason']}: {m['body']['detail']}", file=sys.stderr)
        b = report["body"]
        print(f"\n=== {b['outcome']} ===\n{b['summary']}\n")
        await _wait_for_reviews(d, sub["task_id"], timeout)
        from codedoctor.agents import orchestration as orch

        for child in orch.children(d.s, sub["task_id"]):  # the supervisors' reports (ADR 0016: they report for the hands)
            rep = orch.report_of(d.s, child["id"])
            if rep and orch.body_of(child).get("review_of"):
                print(f"=== {child['agent']}: {rep['outcome']} ===\n{rep['summary']}\n")
        if b.get("claims"):
            print("claims:", ", ".join(f"{c} [{(d.s.claims.get(c) or {}).get('status', '?')}]" for c in b["claims"]))
        if b.get("evidence"):
            print("evidence:\n  " + "\n  ".join(b["evidence"]))
        print("usage:", json.dumps(b.get("usage", {})))
        return 0 if b["outcome"] == "done" else 1
    finally:
        await d.stop()


def _err(text: str) -> None:
    print(text, file=sys.stderr)


def _duration(seconds: float) -> str:
    m, s_ = divmod(int(seconds), 60)
    return f"{m} 分 {s_} 秒" if m else f"{s_} 秒"


def _print_result(r: dict, as_json: bool = False) -> None:
    if as_json:
        _print(r)
        return
    u = r.get("usage") or {}
    tokens = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
    print(f"\n=== {r['status']} === {r['title']}  （{r['task_id']}）")
    if u.get("wall_ms") or tokens:
        print(f"用时 {_duration((u.get('wall_ms') or 0) / 1000)} · 入口 agent 的 token {tokens:,}")
    if r.get("answer"):
        print("\n最终回答：\n" + r["answer"].strip())
    if r["team"]:
        print("\n团队：")
        for m in r["team"]:
            part = ("复查" + (f"（{m['part']}）" if m["part"] else "")) if m["review_of"] else (m["part"] or "子任务")
            print(f"  {m['agent']:<14} {part:<10} {m['status']:<8} {m['first_line'][:70]}")
    if r["changes"]:
        print(f"\n改动（{len(r['changes'])} 个文件）：")
        for c in r["changes"]:
            print(f"  {c['path']:<46} +{c['added']} -{c['removed']}  {'、'.join(c['by'])}")
    t = r["tests"]
    if t["runs"] or r["changes"]:
        print(f"\n测试：{t['verdict']} · 系统共跑了 {t['runs']} 次")
        for x in (t["regressions"] or [])[:10]:
            print(f"  改坏：{x}")
    if r["findings"]:
        print("\n侦察兵发现的问题：")
        for f in r["findings"]:
            who = "主力" if f["fixer"] == "主力" else f"补位 {f['fixer']}"
            print(f"  {'已修好' if f['fixed'] else '没通过'}  {f['test']:<30} {f['scout'] or '侦察兵'} 发现，交给{who}修")
    if r["changes"]:
        print(f"\n要撤回这次的改动：codedoctor undo {r['task_id']}")


def _project(args):
    """(config, label) from --config, or --project / the current folder / the most recent project."""
    from codedoctor import interface

    path = getattr(args, "config", None)
    label = path
    if not path:
        proj = interface.find_project(getattr(args, "project", None))
        if proj is None:
            _err("没找到项目。" + (f"没有叫 {args.project!r} 的项目；" if getattr(args, "project", None) else "")
                 + "先在桌面窗口里新建一个项目（或在项目的代码文件夹里运行），或用 --config 指定配置文件。"
                 "已有的项目：codedoctor projects")
            return None, None
        path, label = proj["config"], f"{proj['name']}（{proj.get('root', '')}）"
    try:
        return config_mod.load(path), label
    except (config_mod.ConfigError, OSError, ValueError) as e:
        _err(f"配置有问题（config error）：{e}")
        return None, None


def _task_arg(s, task: str | None) -> str | None:
    if task and task != "last":
        return task
    row = s.db.one("SELECT id FROM tasks WHERE parent_task_id IS NULL ORDER BY created_at DESC LIMIT 1")
    return row["id"] if row else None


async def _fix(cfg, agent: str, instructions: str, timeout: float, as_json: bool, options: dict | None = None) -> int:
    """Run one investigation in this process and print what the team does while it works."""
    import time

    from codedoctor import interface
    from codedoctor.agents.daemon import Daemon

    d = Daemon(cfg, poll_s=0.3)
    await d.start()
    try:
        try:
            sub = d.submit_task(agent, instructions.splitlines()[0][:80] or "调查", instructions, **(options or {}))
        except ValueError as e:  # e.g. a level the chosen engine model does not have
            _err(f"没有开始：{e}")
            return 2
        tid, agent = sub["task_id"], sub.get("agent", agent)  # @CodeCut sent to a head goes to a worker
        a = cfg.agents[agent]
        model = (options or {}).get("model")
        used = f"{model['endpoint']}/{model['model']}（这次调查的所有 Agent）" if model else f"{a.primary.endpoint}/{a.primary.model}"
        if (options or {}).get("engine"):  # the user's Claude Code / Codex does the work, not the agent's model
            from codedoctor import engines

            used = engines.label(options) + "，你自己的订阅"
        thinking = f"；思考强度 {options['reasoning']}" if (options or {}).get("reasoning") else ""
        _err(f"调查 {tid} 交给 {agent}（{used}{thinking}）；Ctrl+C 中断，之后可在窗口里继续执行")
        seq, t0, timed_out = 0, time.monotonic(), False
        while time.monotonic() - t0 < timeout:
            events, seq = interface.progress(d.s, tid, seq)
            for e in events:
                print(f"[{_duration(time.monotonic() - t0):>9}] {e['text']}", flush=True)
            if interface.settled(d.s, tid):
                events, seq = interface.progress(d.s, tid, seq)
                for e in events:
                    print(f"[{_duration(time.monotonic() - t0):>9}] {e['text']}", flush=True)
                break
            await asyncio.sleep(1)
        else:
            timed_out = True  # the answer, or the reviews after it, may still be running: never a success (Haiku check item 14)
            _err(f"等了 {_duration(timeout)} 还没结束，先停在这里；结果之后可以用 codedoctor show {tid} 查看")
        r = interface.result(d.s, tid)
        _print_result(r, as_json)
        ok = not timed_out and r["outcome"] == "done" and r["tests"]["level"] in ("green", "none")
        return 0 if ok else 1
    finally:
        await d.stop()


async def _wait_for_reviews(d, task_id: str, timeout: float) -> None:
    """The guardian re-checks after the answer; a one-shot run waits for that instead of exiting under it."""
    from codedoctor.agents import orchestration as orch

    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        pending = [c for c in orch.children(d.s, task_id) if not orch.settled(d.s, c["id"])]
        if not pending:
            return
        await asyncio.sleep(1)
    print("[still running when the timeout ended: " + ", ".join(c["agent"] for c in pending) + "]", file=sys.stderr)


async def _check(cfg) -> int:
    from codedoctor.models.base import ModelError
    from codedoctor.models.factory import ModelPool

    pool = ModelPool(cfg)
    bad = 0
    try:
        for eid, ep in cfg.endpoints.items():
            try:
                models = await pool.client(eid).list_models()
                used = sorted({c.model for a in cfg.agents.values() for c in (a.primary, *a.fallbacks) if c.endpoint == eid})
                missing = [m for m in used if models and m not in models]
                status = "ok" if not missing else f"reachable, but models not listed: {missing}"
                print(f"{eid:<20} {ep.base_url:<40} {status} ({len(models)} models)")
                bad += bool(missing)
            except ModelError as e:
                print(f"{eid:<20} {ep.base_url:<40} UNREACHABLE: {e}")
                bad += 1
    finally:
        await pool.aclose()
    for a in cfg.agents.values():
        fb = ", ".join(f"{f.endpoint}/{f.model}" for f in a.fallbacks) or "none (agent pauses on failure)"
        print(f"agent {a.id:<16} role={a.role:<14} model={a.primary.endpoint}/{a.primary.model}  fallbacks: {fb}")
    for w in config_mod.independence_warnings(cfg):
        print(f"提醒：{w}")
    return 1 if bad else 0


def _bench(args) -> int:

    from codedoctor.bench import run as bench_run

    suites = bench_run.SUITES if args.suite == "all" else (args.suite,)
    embedding_from = None
    if args.embedding_config:
        embedding_from = config_mod.load(args.embedding_config)
        if embedding_from.embedding is None:
            print(f"{args.embedding_config} has no [memory.embedding]; choose an embedding model there first", file=sys.stderr)
            return 2
    result = bench_run.run(suites, Path(args.scenarios) if args.scenarios else None, label=args.name, embedding_from=embedding_from)
    if args.out:
        for path in bench_run.write(result, Path(args.out), args.name):
            print(path, file=sys.stderr)
    enc = sys.stdout.encoding or "utf-8"  # a Chinese Windows console is GBK, which has no ⚠
    print(bench_run.markdown(result).encode(enc, errors="replace").decode(enc))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):  # a Chinese Windows console is GBK: a model's emoji must not crash the run
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if argv[:1] == ["gui"]:
        from codedoctor import gui

        return gui.main(argv[1:])
    p = argparse.ArgumentParser(prog="codedoctor")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gui", help="desktop window")
    helps = {"fix": "让整支队伍查找并修复问题，终端里实时显示进度", "tasks": "最近的调查",
             "show": "看一次调查的结果（回答、团队、改动、测试、侦察发现）", "undo": "撤回一次调查改动过的文件",
             "projects": "窗口里建过的项目", "serve": "开本地 HTTP API（见 docs/api.md）"}
    for name in ("fix", "tasks", "show", "undo", "projects", "serve", "run", "check", "memory", "journal", "coverage"):
        sp = sub.add_parser(name, help=helps.get(name))
        if name != "projects":
            sp.add_argument("--config", help="配置文件；不写就用当前文件夹所属的项目")
            sp.add_argument("--project", help="项目名（codedoctor projects 里的）")
        if name == "fix":
            sp.add_argument("--agent", help="交给哪个 agent（默认：你在设置里选的协作方式的入口）")
            sp.add_argument("--timeout", type=float, default=3600, help="最多等多少秒（默认 3600）")
            sp.add_argument("--json", action="store_true", help="结果用 JSON 输出（给脚本用）")
            sp.add_argument("--thinking", choices=("off", "low", "medium", "high", "max"),
                            help="这次调查的思考强度（默认：各 Agent 自己的设置）")
            sp.add_argument("--model", help="这次调查所有 Agent 用的模型，写成 服务/模型，例如 deepseek/deepseek-chat")
            sp.add_argument("--with", dest="tools", action="append",
                            choices=("codecut", "code3d", "codesound", "codepage", "codegame", "codedeck", "codedata", "codecad", "codelab", "codetools", "codefilm", "codepdf"),
                            help="这次调查调用的工具（和窗口里的 @ 一样）：codecut = 用 CodeCut 剪视频，code3d = 用 Code3D 和 Blender 做 3D，"
                                 "codesound = 做音乐音效，codepage = 做网页，codegame = 做小游戏，codedeck = 做幻灯片和文档，codedata = 分析数据，"
                                 "codecad = 做打印零件，codelab = 看训练日志，codetools = 几十个小工具，codefilm = 一句话出成片，codepdf = 照片转 PDF、合并、拆分、压缩。有窗口的工具会打开窗口实时显示")
            sp.add_argument("--engine", choices=("claude_code", "codex"),
                            help="交给谁来做：claude_code / codex = 你自己的 Claude Code / Codex（你的订阅）；"
                                 "快照、测试、复查照旧由 Lumen 做")
            sp.add_argument("--engine-model", help="--engine 用它自己的哪个模型，例如 gpt-6.1-sol、opus（默认：它自己的设置）")
            sp.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max", "ultra"),
                            help="--engine 自己的推理档位（Low/Medium/High/Extra High/Max/Ultra，看模型有哪些；默认：它自己的设置）")
            sp.add_argument("--no-window", action="store_true", help="--with 时不打开工具的窗口（从工具里调用时用）")
            sp.add_argument("instructions", help="问题描述，越具体越好")
        if name in ("show", "undo"):
            sp.add_argument("task", nargs="?", default="last", help="调查编号，或 last（默认）")
        if name == "show":
            sp.add_argument("--json", action="store_true")
        if name == "undo":
            sp.add_argument("--yes", action="store_true", help="不再确认")
        if name == "tasks":
            sp.add_argument("-n", type=int, default=20)
        if name == "serve":
            sp.add_argument("--host", default="127.0.0.1")
            sp.add_argument("--port", type=int, default=8765)
            sp.add_argument("--token", help="访问令牌（也可用环境变量 CODEDOCTOR_API_TOKEN）；监听本机以外的地址时必须设")
        if name == "run":
            sp.add_argument("--agent", help="默认：你选的协作方式的入口 agent")
            sp.add_argument("--title")
            sp.add_argument("--timeout", type=float, default=3600)
            sp.add_argument("instructions")
        if name == "memory":
            sp.add_argument("--reader", required=True)
            sp.add_argument("-k", type=int, default=10)
            sp.add_argument("query")
        if name == "journal":
            sp.add_argument("--task", required=True)
    bp = sub.add_parser("bench", help="memory and reasoning bench (scripted models; no project config needed)")
    bp.add_argument("--suite", choices=("all", "memory", "reasoning", "context"), default="all")
    bp.add_argument("--scenarios", help="scenario directory (default: bench/scenarios in the repository)")
    bp.add_argument("--out", help="write <out>/<name>.json and .md (default: print the summary only)")
    bp.add_argument("--name", default="scripted-baseline")
    bp.add_argument("--embedding-config", help="your project config: its memory.embedding model (your choice) is used for the M6 "
                                               "row; the sample scenarios' notes are sent to that endpoint")
    args = p.parse_args(argv)

    if args.cmd == "bench":
        return _bench(args)

    if args.cmd == "projects":
        from codedoctor import interface

        items = interface.projects()
        if not items:
            print("还没有项目：先在桌面窗口里新建一个。")
        for i in items:
            print(f"{i['name']:<20} {i.get('root', ''):<50} {i['config']}")
        return 0

    cfg, where = _project(args)
    if cfg is None:
        return 2
    _err(f"项目：{where}")
    from codedoctor import interface
    from codedoctor.store.lock import AlreadyRunning

    if args.cmd in ("serve", "run", "fix", "check"):
        agent = getattr(args, "agent", None) or interface.entry_agent(cfg)
        if args.cmd in ("run", "fix") and agent not in cfg.agents:
            _err(f"没有叫 {agent!r} 的 agent；这个项目有：{', '.join(cfg.agents)}")
            return 2
        try:
            if args.cmd == "serve":
                import os

                import uvicorn

                from codedoctor.api import create_app

                token = args.token or os.environ.get("CODEDOCTOR_API_TOKEN")
                if args.host not in ("127.0.0.1", "localhost", "::1") and not token:
                    _err("监听本机以外的地址时必须设访问令牌（--token 或 CODEDOCTOR_API_TOKEN）：这个接口能改你的代码。")
                    return 2
                uvicorn.run(create_app(cfg, token=token), host=args.host, port=args.port)
                return 0
            if args.cmd == "fix":
                if not cfg.permissions.write_files:
                    _err("提醒：这个项目没有允许改代码（设置 → 改代码与测试），这次只会诊断、不会修改文件。")
                options: dict = {"reasoning": args.thinking} if args.thinking else {}
                if args.engine:
                    if args.thinking:
                        _err("--thinking 是 Lumen 自己的思考强度；交给 Claude Code / Codex 时用 --effort（它自己的档位）")
                        return 2
                    options["engine"] = args.engine
                    if args.engine_model:
                        options["engine_model"] = args.engine_model
                    if args.effort:
                        options["engine_effort"] = args.effort
                elif args.engine_model or args.effort:
                    _err("--engine-model / --effort 只和 --engine 一起用")
                    return 2
                if args.tools:
                    from codedoctor import makers, model3d, video

                    for t in args.tools:
                        if t in makers.MAKERS and makers.home(t) is None:
                            _err(f"没有找到 {makers.MAKERS[t].name}（设 {t.upper()}_HOME，或放在 Lumen 旁边的 tools/{t}）")
                            return 2
                    if "codecut" in args.tools and video.home() is None:
                        _err("没有找到 CodeCut（设 CODECUT_HOME，或放在 Lumen 旁边的 tools/codecut）")
                        return 2
                    if "code3d" in args.tools and model3d.home() is None:
                        _err("没有找到 Code3D（设 CODE3D_HOME，或放在 Lumen 旁边的 tools/code3d）")
                        return 2
                    here, root = Path.cwd().resolve(), Path(cfg.root).resolve()
                    if not (args.config or args.project) and here != root and root not in here.parents:
                        _err(f"这个文件夹不在任何 Lumen 项目里（找到的是 {where}，代码文件夹 {root}）。"
                             "先在 Lumen 窗口里为视频所在的文件夹新建一个项目（选好模型），或用 --project 指定。")
                        return 2
                    options["tools"] = list(dict.fromkeys(args.tools))
                    if not args.no_window:
                        if "codecut" in args.tools:
                            video.open_window(cfg.root)
                        if "code3d" in args.tools:
                            model3d.open_window(cfg.root)
                        for t in args.tools:
                            if t in makers.MAKERS:
                                makers.open_window(t, cfg.root)
                if args.model:
                    endpoint, _, model = args.model.partition("/")
                    if endpoint not in cfg.endpoints or not model:
                        _err(f"--model 要写成 服务/模型；这个项目的服务有：{', '.join(cfg.endpoints)}")
                        return 2
                    options["model"] = {"endpoint": endpoint, "model": model}
                return asyncio.run(_fix(cfg, agent, args.instructions, args.timeout, args.json, options))
            if args.cmd == "run":
                return asyncio.run(_run(cfg, agent, args.title or args.instructions[:80], args.instructions, args.timeout))
        except AlreadyRunning:
            _err("这个项目正在桌面窗口里打开（同一个项目同时只能有一个服务在跑）。请关掉窗口再用终端，"
                 "或者在窗口里提问；只读的命令（tasks / show）不受影响。")
            return 3
        except KeyboardInterrupt:
            _err("已中断。没做完的任务会标成“中断”，之后可以在窗口里继续执行。")
            return 130
    if args.cmd == "check":
        return asyncio.run(_check(cfg))

    from codedoctor.services import Services

    s = Services.open(cfg)
    try:
        if args.cmd == "tasks":
            rows = s.db.query("SELECT id, agent, title, state, outcome, created_at FROM tasks WHERE parent_task_id IS NULL "
                              "ORDER BY created_at DESC LIMIT ?", (args.n,))
            from codedoctor.ui_text import local_time, task_status

            if not rows:
                print("还没有调查。")
            for r in rows:
                print(f"{local_time(r['created_at'])}  {task_status(dict(r)):<10} {r['id']}  {r['title'][:60]}")
        elif args.cmd == "show":
            tid = _task_arg(s, args.task)
            r = interface.result(s, tid) if tid else None
            if r is None:
                _err("没有这次调查。最近的调查：codedoctor tasks")
                return 2
            _print_result(r, args.json)
        elif args.cmd == "undo":
            from codedoctor import workspace

            tid = _task_arg(s, args.task)
            r = interface.result(s, tid) if tid else None
            if r is None:
                _err("没有这次调查。最近的调查：codedoctor tasks")
                return 2
            if not interface.settled(s, tid):
                _err("这次调查还没结束，结束后才能撤回。")
                return 2
            print(f"撤回 {tid}（{r['title']}）改动过的 {len(r['changes'])} 个文件；之后又被改过的文件不会动。")
            if not args.yes and input("确定撤回？[y/N] ").strip().lower() not in ("y", "yes", "是"):
                print("没有撤回。")
                return 1
            out = workspace.revert(s, tid)
            print(f"已恢复 {len(out['restored'])} 个、删除新建的 {len(out['removed'])} 个；跳过 {len(out['skipped'])} 个")
            for x in out["skipped"][:20]:
                print(f"  跳过 {x['path']}：{x['why']}")
        elif args.cmd == "memory":
            from codedoctor.memory import related as related_memory

            found = asyncio.run(related_memory.recall_async(s, args.query, reader=args.reader, data_class=cfg.code_data_class,
                                                            k=args.k))
            _print([{"score": round(r.score, 3), "flags": r.flags, "via": r.via, "meaning": r.meaning, **r.note} for r in found])
        elif args.cmd == "journal":
            _print(s.journal.read(task_id=args.task, limit=100000))
        elif args.cmd == "coverage":
            from codedoctor.telemetry import TelemetryStore

            labels = {"healthy": "正常采集", "degraded": "采集异常", "declared": "已接入", "not_instrumented": "未接入"}
            for row in TelemetryStore(s).coverage_status()["rows"]:
                where = f"{row['service']}/{row['layer']}" + (f"  [{row['template']} {row['stage']}]" if "stage" in row else "")
                print(f"{labels[row['status']]:<6} {where:<50} {row['reason']}")
    finally:
        s.db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
