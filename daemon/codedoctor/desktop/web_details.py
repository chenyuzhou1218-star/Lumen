"""详细 in React (web/src/Details.jsx): everything the Qt task page showed around an answer, as data for the page.

Each panel becomes a section of one shape, so that the page draws them all alike:

    {"key", "title", "chips": [{"text", "tone"}], "note", "progress": {"done", "total"},
     "rows": [{"cells": [{"text", "tone", "mono"}]}],
     "items": [{"chips": [...], "title", "sub", "lines": [{"text", "tone"}], "image": data-url}],
     "more": {"head", "lines": [...]}}

tone: "good", "bad", "warn", "info" or "" (quiet). The words are the Qt page's own (anomaly_view, changes_view, cluster_view,
computer_view, task_view), translated where they reach the page. The workspace overview (ADR 0013) is lists with their
details asked for one at a time (workspace_rows, workspace_detail), and its undo.
"""

from __future__ import annotations

import base64
import json
import time

from codedoctor.agents import orchestration as orch
from codedoctor.desktop import locale

t = locale.t


def _chip(text: str, tone: str = "") -> dict:
    return {"text": t(text), "tone": tone}


def _line(text: str, tone: str = "") -> dict:
    return {"text": t(text), "tone": tone}


def _image(daemon, ev_id: str | None) -> str:
    """A screenshot from the evidence store, as a data URL the page can show (small ones only)."""
    if not ev_id or daemon.s.evidence.check(ev_id) != "ok":
        return ""
    data = daemon.s.evidence.content(ev_id)
    if len(data) > 3_000_000:
        return ""
    kind = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{kind};base64,{base64.b64encode(data).decode()}"


# --- the panels ------------------------------------------------------------------------------------------------------------

def _claims(daemon, task_id: str) -> dict | None:
    from codedoctor.ui_text import CLAIM_CN, LEVEL_CN, VERDICT_CN

    claims, stack = [], [task_id]
    while stack:
        tid = stack.pop()
        claims += daemon.s.claims.by_task(tid)
        stack += [c["id"] for c in orch.children(daemon.s, tid)]
    if not claims:
        return None
    tone = {"supported": "good", "refuted": "bad", "proposed": "warn", "needs_revalidation": "warn"}
    items = []
    for c in claims:
        reviews = daemon.s.claims.reviews(c["id"])
        rv = "；".join(f"{r['reviewer']} {t(VERDICT_CN.get(r['verdict'], r['verdict']))}" for r in reviews) or t("还没有独立复查")
        items.append({"chips": [_chip(CLAIM_CN.get(c["status"], c["status"]), tone.get(c["status"], "")),
                                _chip(LEVEL_CN.get(c["evidence_level"], c["evidence_level"]))],
                      "title": c["statement"]["text"], "sub": c["id"],
                      "lines": [{"text": f"{t('提出者')} {c['author']['id']} · {t('证据 {0} 条').replace('{0}', str(len(c.get('evidence', []))))} · {t('复查：')}{rv}", "tone": ""}]})
    return {"key": "claims", "title": t("结论（{0}）").replace("{0}", str(len(claims))), "note": t("只有“成立”是经过独立复查的事实"), "items": items}


def _changes(daemon, task_id: str) -> dict | None:
    from codedoctor.changes import collect, findings, verdict

    info = collect(daemon.s, task_id)
    if not info["files"] and info["runs"] <= 0:
        return None
    text, colour = verdict(info)
    tone = "good" if "通过" in text and "没通过" not in text else "bad" if ("改坏" in text or "没通过" in text) else "warn"
    last = info["last"] or {}
    detail = "，".join(x.split("::")[-1] for x in last["regressions"][:6]) if last.get("regressions") else ""
    rows = [{"cells": [{"text": path, "mono": True}, {"text": f"+{add}", "tone": "good"}, {"text": f"-{rem}", "tone": "bad"},
                       {"text": "、".join(sorted(agents))}]} for path, (add, rem, agents) in sorted(info["files"].items())]
    items = []
    for f in findings(info):
        who = t("主力修") if f["fixer"] == "主力" else t("补位 {0} 修").replace("{0}", str(f["fixer"]))
        items.append({"chips": [_chip("已修好" if f["fixed"] else "还没通过", "good" if f["fixed"] else "warn")], "title": f["test"],
                      "sub": f"{f['scout'] or t('侦察兵')} {t('发现')} · {who}", "lines": []})
    return {"key": "changes", "title": t("改动清单"), "chips": [_chip(text, tone)],
            "note": (f"{detail} · " if detail else "") + t("系统共跑了 {0} 次测试").replace("{0}", str(info["runs"])), "rows": rows, "items": items}


ANOMALY_TONE = {"new": "bad", "fix_now": "bad", "expand": "info", "confirm": "warn", "resolved": "good", "backlog": ""}


def anomaly_chips(anomalies: list) -> list:
    from codedoctor.agents.anomalies import STATUS_CN

    by: dict[str, int] = {}
    for a in anomalies:
        by[a["status"]] = by.get(a["status"], 0) + 1
    return [_chip(f"{t(STATUS_CN[k])} {v}", ANOMALY_TONE.get(k, "")) for k, v in sorted(by.items(), key=lambda kv: list(STATUS_CN).index(kv[0]))]


def anomaly_item(a: dict) -> dict:
    """One anomaly as an item of a section (the answer's 详细, and the 异常收件箱 page)."""
    from codedoctor.agents.anomalies import DECISIONS, KINDS, REASONING_CN, SIZE_CN, STATUS_CN

    tone = ANOMALY_TONE
    d = a.get("decision") or {}
    heads = [_chip(STATUS_CN[a["status"]], tone.get(a["status"], "")), _chip(KINDS.get(a["kind"], a["kind"]))]
    if a["urgent"]:
        heads.append(_chip("重大", "bad"))
    if a["hypothesis"]:
        heads.append(_chip("假设，待验证", "warn"))
    if len(a["occurrences"]) > 1:
        heads.append(_chip(t("出现 {0} 次").replace("{0}", str(len(a["occurrences"])))))
    sub = (t("表面") + f" {t(SIZE_CN[a['surface']])} · " + (f"{t('耦合影响')} {t(SIZE_CN[d['coupling_impact']])} → {t(d['handling'])}（P{d['priority']}）"
                                                         if d else t("等待逻辑首脑决策")) + f" · {t('上报：')}{a['reported_by']}")
    lines = [{"text": t("观察到：") + a["observed"], "tone": ""}]
    if a["where"]:
        lines.append({"text": t("位置：") + "，".join(a["where"]), "tone": "quiet"})
    if a["evidence"]:
        lines.append({"text": t("证据：") + "，".join(a["evidence"][:12]), "tone": "quiet"})
    if a.get("origin_worker"):
        lines.append({"text": t("来自 {0} 的工作：复核必须交给另一个执行者").replace("{0}", a["origin_worker"]), "tone": "quiet"})
    if d:
        lines.append({"text": f"{t('首脑决策：')}{t(DECISIONS[d['decision']])}（{d['by']}）——{d['rationale']}", "tone": ""})
        lines += [{"text": f"· {t(REASONING_CN.get(k, k))}：{v}", "tone": "quiet"} for k, v in d["reasoning"].items()]
        basis = d["basis"]
        if basis["evidence"] or basis["hypothesis"]:
            lines.append({"text": t("影响依据：") + ("，".join(basis["evidence"]) if basis["evidence"] else
                                                 f"{t('假设')}“{basis['hypothesis']}”，{t('证伪方法：')}{basis['falsification']}"), "tone": "quiet"})
    if a.get("links"):
        lines.append({"text": t("后续任务：") + "，".join(f"{x['task_id']}（{x['agent']}）" for x in a["links"]), "tone": "quiet"})
    if a.get("resolution"):
        r = a["resolution"]
        lines.append({"text": (t("确认是预期行为：") if r["by_design"] else t("已解决：")) + r["note"]
                      + (f"（{t('依据结论')} {', '.join(r['claims'])}）" if r["claims"] else ""), "tone": "good"})
    if a.get("recurrences"):
        lines.append({"text": t("之后在类似位置又出现 {0} 次，已要求首脑重新评估是否有共同根因。").replace("{0}", str(len(a["recurrences"]))), "tone": "warn"})
    lines.append({"text": f"{a['id']} · {t('记录永不删除')}", "tone": "quiet"})
    return {"chips": heads, "title": a["title"], "sub": sub, "lines": lines, "folded": True}


def _anomalies(daemon, task_id: str) -> dict | None:
    from codedoctor.agents.anomalies import DECISIONS, KINDS, REASONING_CN, SIZE_CN, STATUS_CN

    anomalies = daemon.s.anomalies.for_root(task_id)
    if not anomalies:
        return None
    chips = anomaly_chips(anomalies)
    order = {k: i for i, k in enumerate(STATUS_CN)}
    items = [anomaly_item(a) for a in sorted(anomalies, key=lambda a: (order[a["status"]], (a.get("decision") or {}).get("priority", 9), not a["urgent"]))[:60]]
    note = t("零遗漏：Agent 发现的任何异常都会写进首脑的收件箱；重大的立即唤醒首脑。")
    if len(anomalies) > 60:
        note += " " + t("另有 {0} 条（已解决或已延后）没有显示。").replace("{0}", str(len(anomalies) - 60))
    return {"key": "anomalies", "title": t("异常与首脑决策"), "chips": chips, "note": note, "items": items}


def _checklist(daemon, task_id: str) -> dict | None:
    from codedoctor.agents.anomalies import CHECK_CN  # the checklist's own words (not the business checks' in ui_text)

    items = daemon.s.anomalies.checklist(task_id)
    if not items:
        return None
    done = sum(i["status"] == "confirmed" for i in items)
    counted = sum(i["status"] != "not_applicable" for i in items)
    tone = {"confirmed": "good", "not_applicable": "", "pending": "warn"}
    rows = []
    for i in items:
        sub = t(CHECK_CN[i["status"]])
        if i["status"] == "not_applicable":
            sub += "：" + i["not_applicable"]["reason"]
        elif i["supported"]:
            sub += f"（{t('结论')} " + "，".join(i["supported"][:4]) + "）"
        elif i["claims"]:
            sub += f"（{t('结论')} " + "，".join(i["claims"][:4]) + f" {t('还没被监督者确认')}）"
        mark = {"confirmed": "☑", "not_applicable": "⊘", "pending": "◐"}.get(i["status"], "☐")
        rows.append({"cells": [{"text": mark, "tone": tone.get(i["status"], "")}, {"text": i["title"]}, {"text": sub, "tone": "quiet"}]})
    open_ = any(i["status"] in ("open", "pending") for i in items)
    return {"key": "checklist", "title": t("细节审查清单"), "chips": [_chip(t("{0} / {1} 项已完成").replace("{0}", str(done)).replace("{1}", str(counted)))],
            "progress": {"done": done, "total": max(counted, 1)}, "rows": rows,
            "note": (t("仍有未完成的检查项目") + " · " if open_ else "") +
            t("完成状态由证据自动确认：只有经过监督者独立复查、状态为“成立”的结论才能勾选，AI 自己说完成不算。")}


def _actions(daemon, task_id: str) -> dict | None:
    from codedoctor.desktop.computer_view import STATUS_CN, describe_cn

    if daemon.s.computer is None:
        return None
    acts = daemon.s.computer.actions(task_ids=orch.tree(daemon.s, task_id), limit=300)
    if not acts:
        return None
    tone = {"executed": "good", "refused": "bad", "denied": "bad", "user_denied": "bad", "failed": "bad", "pending_user": "warn", "pending_guardian": "warn"}
    done = sum(1 for a in acts if a["status"] == "executed")
    items = []
    for a in reversed(acts):
        lines = [{"text": t("目的：") + a["intent"], "tone": "quiet"}]
        lines += [{"text": f"{e['by']}：{e['note']}", "tone": "quiet"} for e in a.get("events", [])
                  if e["what"] in ("refused", "denied", "failed", "guardian_deny", "guardian_needs_user", "user_denied", "no_guardian")]
        after = daemon.s.computer.shot(a["after"], a["task_id"]) if a.get("after") else None
        items.append({"chips": [_chip(STATUS_CN.get(a["status"], a["status"]), tone.get(a["status"], ""))], "title": f"{a['agent']} · {t(describe_cn(a))}",
                      "sub": "", "lines": lines, "image": _image(daemon, after["evidence"]) if after else ""})
    return {"key": "actions", "title": t("电脑操作（{0} 个，已执行 {1} 个）").replace("{0}", str(len(acts))).replace("{1}", str(done)),
            "note": t("每一步都先经过程序检查和监督员批准"), "items": items}


def _investigation(daemon, task_id: str) -> dict | None:
    from codedoctor.desktop.cluster_view import investigation_for
    from codedoctor.ui_text import CHECK_CN, HYPOTHESIS_CN, PURPOSE_CN, SIGNATURE_CN, blocking_cn

    found = investigation_for(daemon, task_id)
    if not found:
        return None
    doc, status = found
    plan = doc["plan"]
    ok = status["delivery_allowed"]
    lines = [_line("结论只在已声明的受控实验场景内成立，不是普遍的因果证明；结构上的共同上游只是线索，不是已确认的原因。", "quiet")]
    if plan.get("symptoms"):
        lines.append({"text": t("症状：") + "；".join(plan["symptoms"]), "tone": ""})
    lines += [{"text": "• " + t(blocking_cn(r)), "tone": "bad"} for r in status["blocking_reasons"]]
    tone = {"refuted_in_declared_scope": "", "compatible_not_proven": "good", "untested": "warn"}
    items = []
    for h in status["hypothesis_ledger"]:
        detail = []
        for kind, xs in ((t("支持"), h["support"]), (t("反驳"), h["refutations"])):
            for s in xs:
                detail.append({"text": f"{kind}：{t('检查')} {s['check']} {t('预测')}“{t(SIGNATURE_CN.get(s['predicted'], s['predicted']))}”，"
                                       f"{t('实际')}“{t(SIGNATURE_CN.get(s['observed'], s['observed']))}”（{t('{0} 条原始记录').replace('{0}', str(len(s['evidence'])))}）", "tone": "quiet"})
        items.append({"chips": [_chip(HYPOTHESIS_CN.get(h["state"], h["state"]), tone.get(h["state"], ""))], "title": h["statement"],
                      "sub": f"{h['id']} · {t('候选位置：')}{h['candidate']}", "lines": detail})
    predictions = {c["id"]: c for c in plan["checks"]}
    rows = [{"cells": [{"text": c["id"], "mono": True}, {"text": t(PURPOSE_CN.get(c["purpose"], c["purpose"]))},
                       {"text": predictions.get(c["id"], {}).get("scenario", ""), "tone": "quiet"}, {"text": t(CHECK_CN.get(c["state"], c["state"]))},
                       {"text": t(SIGNATURE_CN.get(c["observed"], "还没有结果")) if c["observed"] else t("还没有结果"), "tone": "quiet"}]}
            for c in status["checks"]]
    if status.get("next_check"):
        pairs = status["next_check_distinguishes_pairs"]
        lines.append({"text": (t("下一项最能区分假设的检查：{0}（能区分 {1} 对假设）").replace("{0}", status["next_check"]).replace("{1}", str(pairs))) if pairs
                      else t("下一项待做的检查：{0}（不用于区分假设）").replace("{0}", status["next_check"]), "tone": "info"})
    if status.get("structural_analysis_truncated"):
        lines.append(_line("注意：结构分析达到上限被截断，没列出的路径不代表不存在。", "warn"))
    ev = status["evidence"]
    return {"key": "investigation", "title": t("业务实验调查"), "chips": [_chip("可以交付" if ok else "交付被阻止", "good" if ok else "bad")],
            "note": status["id"], "lines": lines, "items": items, "rows": rows,
            "more": {"head": t("原始实验记录 {0} 条").replace("{0}", str(len(ev))) + f" · {t('代码版本')} {status['code_version'][:19]}…",
                     "lines": [{"text": x, "tone": "quiet"} for x in ev] or [_line("（还没有）", "quiet")]}}


def _picture(daemon, task: dict) -> str:
    """@Code3D and the other making tools: what the team made, as a picture in the answer."""
    from codedoctor import makers, model3d
    from codedoctor.ui_text import parse_ts

    called = orch.body_of(task).get("toolsets") or []
    path = None
    if "code3d" in called:
        path = model3d.result_picture(daemon.s.config.root, parse_ts(task["created_at"]))
    elif set(called) & set(makers.IDS):
        path = makers.result_picture(called, daemon.s.config.root, parse_ts(task["created_at"]))
    if path is None:
        return ""
    from PySide6.QtCore import QUrl

    return QUrl.fromLocalFile(str(path)).toString()


def details_json(win, task_id: str) -> dict:
    """详细 of one turn: its header line, the escalations put plainly, and every panel that has something to show."""
    from codedoctor.desktop.task_view import _readable_escalation
    from codedoctor.ui_text import ESCALATION_CN, duration, parse_ts, task_status

    d = win.d
    task = d.task(task_id)
    if task is None:
        return {"missing": True}
    status = task_status(task)
    fixing = d.s.config.permissions.write_files and not orch.body_of(task).get("chat")
    if fixing and task["state"] == "finished" and task["outcome"] == "done":
        from codedoctor.changes import collect, verdict

        text, _ = verdict(collect(d.s, task_id))
        if "改坏" in text or "没通过" in text:
            status = "完成 · 测试未全过"  # the answer may say done; the system's test run says otherwise
    usage = task["usage"] or {}
    elapsed = time.time() - parse_ts(task["created_at"]) if task["state"] != "finished" else (usage.get("wall_ms") or 0) / 1000
    whole, cached = orch.tree_tokens(d.s, task_id), orch.tree_cached(d.s, task_id)
    escalations, seen = [], set()
    for m in task["messages"]:
        if m["kind"] == "escalation" and m["body"].get("task_id") == task_id:
            text = f"{t(ESCALATION_CN.get(m['body']['reason'], m['body']['reason']))}\n{_readable_escalation(d, m['body'])}"
            if text not in seen:
                seen.add(text)
                escalations.append(text)
    sections = [s for s in (_investigation(d, task_id), _actions(d, task_id), _anomalies(d, task_id),
                            _changes(d, task_id) if fixing else _checklist(d, task_id), _claims(d, task_id)) if s]
    return {"task_id": task_id, "status": t(status), "info": f"{t(duration(elapsed))} · token {max(0, whole - cached):,}",
            "cached": cached, "escalations": escalations, "sections": sections, "picture": _picture(d, task),
            "workspace": orch.tree(d.s, task_id) is not None}


# --- 工作区一览 (ADR 0013): lists, a detail for one row at a time, and the undo of an investigation's changes ------------------

TABS = ("changes", "timeline", "files", "commands", "findings")


def workspace_rows(win, task_id: str, tab: str) -> dict:
    from codedoctor import workspace
    from codedoctor.desktop.computer_view import STATUS_CN as ACTION_CN, describe_cn
    from codedoctor.desktop.workspace_view import KIND_CN
    from codedoctor.ui_text import CLAIM_CN, describe_tool_call, local_time

    s = win.d.s
    if tab == "changes":
        ch = workspace.changes(s, task_id)
        if ch is None:
            return {"note": t("这个调查没有项目快照（快照从 ADR 0013 之后开始的调查才有）。"), "rows": [], "undo": False}
        span = t("开始 → 结束") if ch["against"] == "end" else t("开始 → 现在（调查还在进行）")
        note = (t("调查开始以来（{0}）：新增 {1}、修改 {2}、删除 {3} 个文件。").replace("{0}", span).replace("{1}", str(len(ch["added"])))
                .replace("{2}", str(len(ch["modified"]))).replace("{3}", str(len(ch["deleted"])))
                + t("快照只能看出文件变了，看不出是谁改的：期间你自己或其他程序的修改也会算在内。") + (t("（项目文件太多，快照被截断。）") if ch["truncated"] else ""))
        rows = [{"text": p, "mark": "+", "tone": "good"} for p in ch["added"]] + \
               [{"text": m["path"], "mark": "~", "tone": "warn", "binary": not m["text"]} for m in ch["modified"]] + \
               [{"text": p, "mark": "-", "tone": "bad"} for p in ch["deleted"]]
        return {"note": note, "rows": rows, "undo": ch["against"] == "end" and bool(rows)}
    if tab == "timeline":
        rows = []
        for it in workspace.timeline(s, task_id):
            if it["kind"] == "tool":
                mark = "…" if it["ok"] is None else ("✓" if it["ok"] else "✗")
                rows.append({"text": f"{it['agent']}  {t(describe_tool_call(it['tool'], it['arguments']))}", "mark": mark, "at": local_time(it["at"]),
                             "tone": "" if it["ok"] is not False else "bad"})
            else:
                rows.append({"text": f"{it['agent']}  [{t(KIND_CN.get(it['kind'], it['kind']))}] {it['text'][:160]}", "mark": "·", "at": local_time(it["at"]), "tone": ""})
        return {"note": "", "rows": rows}
    if tab == "files":
        return {"note": "", "rows": [{"text": f["path"], "sub": f"{', '.join(f['ranges'][:6])}{' …' if len(f['ranges']) > 6 else ''} · {', '.join(f['agents'])}", "mark": ""}
                                     for f in workspace.files_read(s, task_id)]}
    if tab == "commands":
        rows = []
        for c in workspace.commands(s, task_id):
            mark = "…" if c["ok"] is None else ("✓" if c["ok"] else "✗")
            rows.append({"text": f"$ {c['command'][:160]}", "sub": c["agent"] + (f" · {t('退出码')} {c['exit_code']}" if c["exit_code"] is not None else ""),
                         "mark": mark, "at": local_time(c["at"]), "tone": "bad" if c["ok"] is False else "", "_sort": c["at"]})
        if s.computer is not None:
            for a in reversed(s.computer.actions(task_ids=orch.tree(s, task_id), limit=500)):
                if a["kind"] != "terminal":
                    rows.append({"text": t(describe_cn(a)), "sub": f"{a['agent']} · {t(ACTION_CN.get(a['status'], a['status']))}", "mark": "⌖",
                                 "at": local_time(a["created_at"]), "tone": "", "_sort": a["created_at"]})
        rows.sort(key=lambda r: r.pop("_sort"))
        return {"note": "", "rows": rows}
    cn = workspace.claims_and_notes(s, task_id)
    rows = [{"text": c["statement"]["text"][:200], "sub": f"{t(CLAIM_CN.get(c['status'], c['status']))} · {c['author']['id']}", "mark": "◆"} for c in cn["claims"]]
    rows += [{"text": n["text"][:200], "sub": f"{t('记忆')} · {n['owner']}", "mark": "◇"} for n in cn["notes"]]
    return {"note": "", "rows": rows}


def workspace_detail(win, task_id: str, tab: str, index: int) -> dict:
    """The detail of one row: a diff, a step's arguments and result, a file's excerpts, a command's output, a claim."""
    from codedoctor import workspace
    from codedoctor.desktop.computer_view import STATUS_CN as ACTION_CN, describe_cn
    from codedoctor.ui_text import CLAIM_CN

    s = win.d.s
    if tab == "changes":
        ch = workspace.changes(s, task_id) or {"added": [], "modified": [], "deleted": []}
        entries = [("added", p, True) for p in ch["added"]] + [("modified", m["path"], m["text"]) for m in ch["modified"]] + \
                  [("deleted", p, True) for p in ch["deleted"]]
        if not 0 <= index < len(entries):
            return {"text": ""}
        kind, path, text = entries[index]
        if kind == "modified" and not text:
            return {"text": t("二进制文件或大于 512 KB 的文件：只记录大小和修改时间，不显示逐行差异。")}
        diff = workspace.diff(s, task_id, path)
        return {"diff": diff} if diff else {"text": t("没有可显示的文本差异（二进制文件，或内容没有保存）。")}
    if tab == "timeline":
        items = workspace.timeline(s, task_id)
        if not 0 <= index < len(items):
            return {"text": ""}
        it = items[index]
        if it["kind"] != "tool":
            return {"text": f"{it['agent']} · {it['task']}\n\n{it['text']}"}
        text = f"{it['agent']} · {t('任务：')}{it['task']}\n\n{t('参数：')}\n{json.dumps(it['arguments'], ensure_ascii=False, indent=1)}"
        if it["result_entry"]:
            payload = s.journal.original(s.journal.get(it["result_entry"])).get("payload")
            text += f"\n\n{t('结果：')}\n" + (payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=1))[:60000]
        else:
            text += "\n\n" + t("（还没有结果）")
        return {"text": text}
    if tab == "files":
        files = workspace.files_read(s, task_id)
        if not 0 <= index < len(files):
            return {"text": ""}
        parts = [f"── {ev.rsplit(':', 1)[-1]}  ({ev})\n" + s.evidence.content(ev).decode("utf-8", errors="replace")
                 for ev in files[index]["evidence"][:5] if s.evidence.check(ev) == "ok"]
        return {"text": "\n\n".join(parts) or t("摘录无法读取。")}
    if tab == "commands":
        rows = [("cmd", c, c["at"]) for c in workspace.commands(s, task_id)]
        if s.computer is not None:
            rows += [("act", a, a["created_at"]) for a in reversed(s.computer.actions(task_ids=orch.tree(s, task_id), limit=500)) if a["kind"] != "terminal"]
        rows.sort(key=lambda r: r[2])
        if not 0 <= index < len(rows):
            return {"text": ""}
        kind, x, _ = rows[index]
        if kind == "cmd":
            return {"text": f"$ {x['command']}\n\n{x['output']}"}
        events = "\n".join(f"{e['at'][11:19]} {e['by']}: {e['what']} {e.get('note', '')}" for e in x.get("events", []))
        return {"text": f"{t(describe_cn(x))}\n{t('目的：')}{x['intent']}\n{t('状态：')}{t(ACTION_CN.get(x['status'], x['status']))}\n\n{events}"}
    cn = workspace.claims_and_notes(s, task_id)
    items = [("claim", c) for c in cn["claims"]] + [("note", n) for n in cn["notes"]]
    if not 0 <= index < len(items):
        return {"text": ""}
    kind, x = items[index]
    if kind == "claim":
        ev = "\n".join(f"- {r['id']}  ({r['role']}) {r.get('shows', '')}" for r in x.get("evidence", []))
        st = x["statement"]
        return {"text": f"{x['id']}  [{t(CLAIM_CN.get(x['status'], x['status']))}]  {x['claim_type']} / {x['evidence_level']}\n"
                        f"{st['text']}\n{st['subject']} -{st['relation']}-> {st['object']}\n\n{t('证据：')}\n{ev or t('无')}"}
    return {"text": f"{x['id']} · {x['owner']} · {x['kind']}\n\n{x['text']}"}


def workspace_undo(win, task_id: str) -> dict:
    """撤回这次调查的所有修改 (ADR 0016): files back as they were when it began; ones changed since it ended are skipped."""
    from codedoctor import workspace

    try:
        res = workspace.revert(win.d.s, task_id)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    lines = [t("恢复 ") + p for p in res["restored"]] + [t("删除（调查中新建的）") + p for p in res["removed"]] + \
            [f"{t('跳过 ')}{x['path']}：{x['why']}" for x in res["skipped"]]
    return {"ok": True, "restored": len(res["restored"]), "removed": len(res["removed"]), "skipped": len(res["skipped"]), "lines": lines}


def remember(win, task_id: str, text: str) -> dict:
    """记住: this answer into the project's long-term memory, for every AI that works here later."""
    d = win.d
    try:
        first = d.s.journal.read(task_id=task_id, limit=1)
        d.s.notes.write(owner="user", scope="project", kind="fact", text=text[:4000], sources=[first[0]["id"]], task_id=task_id,
                        data_class=d.s.config.code_data_class)
    except Exception as e:  # shown on the button
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"ok": True}
