"""Run the bench suites and write results as JSON (complete) and Markdown (readable summary).

Results contain no ids, timestamps or wall-clock times, so two runs of the same code give the
same file and a diff shows exactly what a change did to the scores.
"""

from __future__ import annotations

import json
from pathlib import Path

from codedoctor.bench import context, memory, reasoning

SUITES = ("memory", "reasoning", "context")


def run(suites=SUITES, scenarios_dir: Path | None = None, label: str = "scripted-baseline", embedding_from=None) -> dict:
    models = "脚本模型（bench/policies.py）"
    if embedding_from is not None:
        models += f"；嵌入模型 {embedding_from.embedding.endpoint}/{embedding_from.embedding.model}（用户指定）"
    else:
        models += "，没有调用任何真实模型"
    out: dict = {"label": label, "models": models}
    if "memory" in suites:
        out["memory"] = memory.run(scenarios_dir, embedding_from)
    if "reasoning" in suites:
        out["reasoning"] = reasoning.run(scenarios_dir)
    if "context" in suites:
        out["context"] = context.run(scenarios_dir)
    return out


def _fmt(v) -> str:
    return "—" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)


def markdown(result: dict) -> str:
    lines = [f"# 评测结果：{result['label']}", "", f"模型：{result['models']}", ""]
    mem = result.get("memory")
    if mem:
        lines += ["## 记忆召回", "", "| 配置 | recall@8 | MRR | 未警示的不可信笔记 | 不可信笔记排在正确笔记前 | 越权可见 | 全对的问题 |",
                  "|---|---|---|---|---|---|---|"]
        for c in mem["configs"]:
            s = mem["summary"][c["id"]]
            lines.append(f"| {c['label']} | {_fmt(s['recall_at_k'])} | {_fmt(s['mrr'])} | {s['unsafe']} | {s['trap_above']} | "
                         f"{s['leaks']} | {s['perfect']}/{s['probes']} |")
        for c in mem.get("not_run", []):
            lines.append(f"| {c['label']} | 未评测：{c['why']} | | | | | |")
        last = mem["configs"][-1]["id"]
        for sc in mem["scenarios"]:
            lines += ["", f"### {sc['id']}：逐题（{mem['configs'][-1]['label']}）", "",
                      "| 问题 | 语言 | recall | RR | 未警示 | 排在前 | 前 5 条 |", "|---|---|---|---|---|---|---|"]
            for p in sc["configs"][last]["probes"]:
                top = ", ".join(t["note"] + ("⚠" if t["warned"] else "") for t in p["top"][:5])
                lines.append(f"| {p['id']} {p['query']} | {p['lang']} | {_fmt(p['recall'])} | {_fmt(p['rr'])} | {p['unsafe']} | "
                             f"{p['trap_above']} | {top} |")
    rea = result.get("reasoning")
    if rea:
        lines += ["", "## 推理：图谱分析（无模型）", ""]
        for st in rea["static"]:
            s = st["summary"]
            lines += [f"- {st['id']}：缺陷检出 {s['defects_detected']}，平均排名 {_fmt(s['mean_defect_rank'])}"
                      f"（共报告 {s['risks_reported']} 条风险，其中 {s['risks_matching_a_known_defect']} 条对应已知缺陷）；"
                      f"共同根因第 1 名命中 {s['common_cause_hit_at_1']}/{s['common_cause_probes']}；影响范围召回 {_fmt(s['impact_recall'])}",
                      "", "| 缺陷 | 检出 | 排名 |", "|---|---|---|"]
            lines += [f"| {d['id']} {d['what']} | {'是' if d['detected'] else '否'} | {_fmt(d['rank'])} |" for d in st["defects"]]
            lines += ["", "| 共同根因 | 期望 | 排名 | 前 3 |", "|---|---|---|---|"]
            lines += [f"| {c['id']} | {c['expect']} | {_fmt(c['rank'])} | {', '.join(c['top3'])} |" for c in st["common_cause"]]
        if rea["agent"]:
            s = rea["summary"]["agent"]
            lines += ["", "## 推理：Agent 端到端（脚本策略）", "",
                      f"合计 {s['runs']} 次运行：根因得分 {_fmt(s['root_cause'])}，错误事实 {s['false_facts']}，覆盖 {_fmt(s['coverage'])}，"
                      f"推理缺陷 {s['defects_present']} 个，系统指出 {s['defects_caught']} 个（{_fmt(s['catch_rate'])}），"
                      f"误报 {s['false_alarms']}；模型调用 {s['model_calls']} 次，约 {s['tokens']} token。", "",
                      "| 场景 / 策略 | 结果 | 根因 | 覆盖 | 推理缺陷 | 系统指出 | 误报 | 调用 |", "|---|---|---|---|---|---|---|---|"]
            for sc in rea["agent"]:
                for r in sc["runs"]:
                    lines.append(f"| {sc['id']} / {r['policy']} | {r['outcome']} | {_fmt(r['root_cause'])} | {_fmt(r['coverage'])} | "
                                 f"{', '.join(r['defects']) or '无'} | {', '.join(r['caught']) or '无'} | "
                                 f"{', '.join(r['false_alarms']) or '无'} | {r['cost']['model_calls']} |")
            lines += ["", "推理缺陷的定义："] + [f"- `{k}`：{v}" for k, v in rea["defect_checks"].items()]
    ctx = result.get("context")
    if ctx:
        lines += ["", "## 上下文（小预算长任务，脚本策略）", "",
                  "| 场景 | 策略 | 结果 | 超出预算的请求 | 峰值 / 预算 | 重写上下文 | 输入字符 | 证据 ID 完整保留 | 证据可找回 | 主张当前状态可见 |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for sc in ctx["scenarios"]:
            for p in sc["policies"].values():
                lines.append(f"| {sc['id']}（{sc['budget_tokens']} token） | {p['label']} | {p['outcome']} | {p['over_budget']}/{p['requests']} | "
                             f"{_fmt(p['peak_share'])} | {p['rewrites']} | {p['input_chars']} | {_fmt(p['evidence_retained'])} | "
                             f"{_fmt(p['evidence_recoverable'])} | {_fmt(p['status_retained'])} |")
    return "\n".join(lines) + "\n"


def write(result: dict, out_dir: Path, name: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j, m = out_dir / f"{name}.json", out_dir / f"{name}.md"
    j.write_bytes((json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    m.write_bytes(markdown(result).encode("utf-8"))
    return j, m
