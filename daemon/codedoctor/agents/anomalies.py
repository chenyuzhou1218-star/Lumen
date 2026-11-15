"""Anomaly inbox, head decisions and the detail checklist of an investigation (ADR 0014).

Zero omission: every anomaly any agent notices - a crash, an intermittent failure, an unclickable button,
a missing pixel, misplaced text, a dropped animation frame, an unusual log warning, a suspected coupling -
is written to the investigation's inbox. Nothing is ever deleted: a repeat of the same anomaly is merged
into it as another occurrence with its own evidence. Urgent ones wake the logic head at once; the rest are
guaranteed to reach its next review, and the dispatch head cannot deliver while any is undecided.

The logic head decides each one (fix now / expand the investigation / backlog / to be confirmed) after the
micro-anomaly questions, and rates its coupling impact; the program, not the model, turns the surface size
and the coupling impact into the handling priority. A large impact needs evidence or an explicit hypothesis
with a falsification test, so an imagined story cannot claim unlimited attention.

A detail-checklist item counts as confirmed only when a claim attached to it is 'supported' (validated and
independently re-checked by a guardian). Agents can attach claims and evidence; they cannot tick a box.
"""

from __future__ import annotations

import hashlib
import json
import re

from codedoctor import ids
from codedoctor.agents import orchestration as orch
from codedoctor.store.db import dumps

KINDS = {
    "crash": "崩溃 / 服务器错误",
    "data_error": "数据库 / 数据错误",
    "flow_failure": "业务流程失败（含偶发）",
    "unclickable": "无法点击 / 无法操作",
    "visual": "界面显示（缺像素、图标、遮挡）",
    "text": "文字内容或位置异常",
    "animation": "动画少帧 / 显示不完整",
    "log_warning": "日志里不寻常的警告",
    "coupling_suspicion": "疑似耦合问题",
    "performance": "性能 / 卡顿",
    "other": "其他",
}
URGENT_KINDS = {"crash", "data_error", "flow_failure"}
DECISIONS = {"fix_now": "立即修复", "expand": "扩大调查", "backlog": "加入待办", "confirm": "标记待确认"}
STATUS_CN = {"new": "待首脑决策", **DECISIONS, "resolved": "已解决"}
DEFERRED = ("backlog", "confirm")
FOLLOW_UP = ("fix_now", "expand")
# (surface, coupling impact) -> (handling, priority 0 = highest)
QUADRANT = {
    ("small", "small"): ("记录并安排局部修复", 3),
    ("small", "large"): ("优先进行系统级调查", 1),
    ("large", "small"): ("优先修复直接故障", 1),
    ("large", "large"): ("立即组织跨模块调查与独立验证", 0),
}
SIZE_CN = {"small": "小", "large": "大"}
# Micro-anomaly reasoning: the questions the logic head must answer before deciding.
REASONING = {
    "expected": "Should it exist / look like this at all? (design, history, earlier versions)",
    "mechanism": "What produces it? (e.g. CSS covering it, rendering failure, a state that never triggered)",
    "interaction": "Does it take part in clicks, event listeners, collision or other logic?",
    "shared_logic": "Do other components use the same rendering / state / logic, so they may have it too?",
    "fix_side_effects": "Could fixing it affect other buttons, coordinates, layout or behaviour?",
}
REASONING_CN = {"expected": "原本应该是这样吗", "mechanism": "产生机制", "interaction": "是否参与交互或逻辑",
                "shared_logic": "其他地方是否用了同样的逻辑", "fix_side_effects": "修改后可能影响什么"}
DEFAULT_CHECKS = [
    ("flow", "功能流程和业务状态"),
    ("coupling", "跨模块耦合与连锁影响"),
    ("ui", "UI 元素完整性与显示位置"),
    ("resolution", "不同分辨率和窗口尺寸"),
    ("edge", "断网、退出、并发等边界条件"),
    ("longrun", "长期运行与异常恢复"),
]
CHECK_CN = {"confirmed": "已由证据确认", "pending": "有证据，等待复查确认", "open": "未完成", "not_applicable": "不适用"}
MAX_ASSESSMENTS = 3  # automatic assessment tasks per investigation; after that the user decides what is left


class AnomalyError(ValueError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _paths(doc: dict) -> set[str]:
    """Files an anomaly points at ('server/shop.py:12' -> 'server/shop.py')."""
    return {w.split(":", 1)[0].split("#", 1)[0].strip().lower() for w in doc.get("where", []) if w.strip()}


class Anomalies:
    def __init__(self, services):
        self.s = services
        self._checked: set[str] = set()  # roots whose checklist rows exist
        with services.db.tx() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS anomalies (
                id TEXT PRIMARY KEY, root_task_id TEXT NOT NULL, status TEXT NOT NULL, urgent INTEGER NOT NULL,
                dedup_key TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, doc TEXT NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS anomalies_root ON anomalies(root_task_id, created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS anomalies_key ON anomalies(root_task_id, dedup_key)")
            c.execute("""CREATE TABLE IF NOT EXISTS detail_checks (
                root_task_id TEXT NOT NULL, item_id TEXT NOT NULL, position INTEGER NOT NULL, doc TEXT NOT NULL,
                PRIMARY KEY (root_task_id, item_id))""")

    # --- storage -------------------------------------------------------------------------------

    def get(self, anomaly_id: str) -> dict | None:
        row = self.s.db.one("SELECT doc FROM anomalies WHERE id = ?", (anomaly_id,))
        return json.loads(row["doc"]) if row else None

    def _save(self, c, doc: dict) -> None:
        doc["updated_at"] = ids.now()
        c.execute("UPDATE anomalies SET status = ?, urgent = ?, updated_at = ?, doc = ? WHERE id = ?",
                  (doc["status"], int(doc["urgent"]), doc["updated_at"], dumps(doc), doc["id"]))

    def for_root(self, root_task_id: str) -> list[dict]:
        return [json.loads(r["doc"]) for r in self.s.db.query(
            "SELECT doc FROM anomalies WHERE root_task_id = ? ORDER BY created_at", (root_task_id,))]

    def recent(self, limit: int = 200) -> list[dict]:
        return [json.loads(r["doc"]) for r in self.s.db.query(
            "SELECT doc FROM anomalies ORDER BY updated_at DESC LIMIT ?", (limit,))]

    def counts(self) -> dict[str, int]:
        return {r["status"]: r["n"] for r in self.s.db.query("SELECT status, COUNT(*) AS n FROM anomalies GROUP BY status")}

    def undecided(self, root_task_id: str) -> list[dict]:
        return [a for a in self.for_root(root_task_id) if a["status"] == "new"]

    def to_reassess(self, root_task_id: str) -> list[dict]:
        """Deferred anomalies (any investigation) that a new anomaly of this one may share a root cause with."""
        out, seen = [], set()
        for a in self.for_root(root_task_id):
            for rid in a.get("related", []):
                r = self.get(rid)
                if r and r["status"] in DEFERRED and r.get("reassess_for") and rid not in seen:
                    seen.add(rid)
                    out.append(r)
        return out

    # --- report -------------------------------------------------------------------------------

    def report(self, *, task_id: str, by: str, role: str, kind: str, title: str, observed: str, surface: str,
               where: list[str] | None = None, entities: list[str] | None = None, evidence: list[str] | None = None,
               hypothesis: bool = False) -> tuple[dict, bool]:
        """(anomaly, merged). merged: it repeated an anomaly already in this investigation's inbox."""
        if kind not in KINDS:
            raise AnomalyError(f"unknown kind {kind!r}; one of {', '.join(KINDS)}")
        if surface not in SIZE_CN:
            raise AnomalyError("surface must be 'small' or 'large'")
        evidence = list(dict.fromkeys(evidence or []))
        bad = [e for e in evidence if self.s.evidence.check(e) != "ok"]
        if bad:
            raise AnomalyError(f"evidence not usable: {', '.join(bad)}; cite only ids your tools returned")
        if not evidence and not hypothesis:
            raise AnomalyError("cite the evidence you observed it in, or set hypothesis=true if it is only a suspicion")
        where = [w.strip() for w in (where or []) if w.strip()][:20]
        entities = [e.strip() for e in (entities or []) if e.strip()][:20]
        root = orch.root_of(self.s, task_id)
        key = hashlib.sha256(f"{kind}\0{_norm(title)}\0{'|'.join(sorted(map(_norm, where)))}".encode()).hexdigest()
        now = ids.now()
        occurrence = {"at": now, "by": by, "task_id": task_id, "observed": observed[:4000], "evidence": evidence,
                      "hypothesis": hypothesis}
        urgent = kind in URGENT_KINDS or surface == "large"
        with self.s.db.tx() as c:
            row = c.execute("SELECT doc FROM anomalies WHERE root_task_id = ? AND dedup_key = ?", (root, key)).fetchone()
            if row is not None:
                doc = json.loads(row[0])
                doc["occurrences"].append(occurrence)
                doc["evidence"] = list(dict.fromkeys(doc["evidence"] + evidence))
                doc["hypothesis"] = doc["hypothesis"] and hypothesis  # evidence once seen stays
                if surface == "large" and doc["surface"] == "small":
                    doc["surface"] = "large"
                    doc["history"].append({"at": now, "by": by, "action": "surface_raised"})
                doc["urgent"] = doc["urgent"] or urgent
                doc["history"].append({"at": now, "by": by, "action": "repeated", "task_id": task_id})
                self._save(c, doc)
                return doc, True
            doc = {
                "id": ids.new_id("anm"), "root_task_id": root, "task_id": task_id, "reported_by": by, "role": role,
                "origin_worker": self._origin_worker(task_id, by, role), "kind": kind, "title": title[:300],
                "observed": observed[:4000], "where": where, "entities": entities, "evidence": evidence,
                "hypothesis": hypothesis, "surface": surface, "urgent": urgent, "status": "new", "decision": None,
                "occurrences": [occurrence], "links": [], "related": [], "created_at": now, "updated_at": now,
                "history": [{"at": now, "by": by, "action": "reported", "task_id": task_id}],
            }
            related = self._related(c, doc)
            doc["related"] = [r["id"] for r in related]
            c.execute("INSERT INTO anomalies (id, root_task_id, status, urgent, dedup_key, created_at, updated_at, doc) "
                      "VALUES (?,?,?,?,?,?,?,?)", (doc["id"], root, "new", int(urgent), key, now, now, dumps(doc)))
            for r in related:  # a deferred anomaly showed up again in a similar place: the head must look at it again
                r.setdefault("recurrences", []).append({"at": now, "anomaly": doc["id"], "root_task_id": root})
                r["reassess_for"] = root
                r["history"].append({"at": now, "by": "system", "action": "similar_symptom", "anomaly": doc["id"]})
                self._save(c, r)
        return doc, False

    def _origin_worker(self, task_id: str, by: str, role: str) -> str | None:
        """The worker whose work the anomaly came from: verification must go to someone else."""
        if role in orch.DELEGATE_ROLES:
            return by
        if role == "guardian":
            row = orch.task_row(self.s, task_id) or {}
            reviewed = orch.body_of(row).get("review_of")
            if reviewed:
                return (orch.task_row(self.s, reviewed) or {}).get("agent")
            sup = self.s.config.agents.get(by)
            return sup.supervises if sup else None
        return None

    def _related(self, c, doc: dict) -> list[dict]:
        paths, ents = _paths(doc), {_norm(e) for e in doc["entities"]}
        if not paths and not ents:
            return []
        out = []
        for (raw,) in c.execute("SELECT doc FROM anomalies WHERE status IN ('backlog', 'confirm') ORDER BY created_at DESC LIMIT 500"):
            other = json.loads(raw)
            if paths & _paths(other) or ents & {_norm(e) for e in other["entities"]}:
                out.append(other)
        return out[:10]

    # --- decide / resolve ---------------------------------------------------------------------

    def decide(self, anomaly_id: str, *, by: str, decision: str, coupling_impact: str, reasoning: dict,
               rationale: str, basis_evidence: list[str] | None = None, basis_hypothesis: str = "",
               falsification: str = "") -> dict:
        doc = self.get(anomaly_id)
        if doc is None:
            raise AnomalyError(f"unknown anomaly {anomaly_id}")
        if doc["status"] == "resolved":
            raise AnomalyError(f"{anomaly_id} is already resolved")
        if decision not in DECISIONS:
            raise AnomalyError(f"decision must be one of {', '.join(DECISIONS)}")
        if coupling_impact not in SIZE_CN:
            raise AnomalyError("coupling_impact must be 'small' or 'large'")
        missing = [k for k in REASONING if len((reasoning or {}).get(k, "").strip()) < 2]
        if missing:
            raise AnomalyError("answer every micro-anomaly question before deciding; missing: "
                               + "; ".join(f"{k} ({REASONING[k]})" for k in missing))
        basis_evidence = list(dict.fromkeys(basis_evidence or []))
        bad = [e for e in basis_evidence if self.s.evidence.check(e) != "ok"]
        if bad:
            raise AnomalyError(f"evidence not usable: {', '.join(bad)}")
        if coupling_impact == "large" and not basis_evidence and not (basis_hypothesis.strip() and falsification.strip()):
            raise AnomalyError("a large coupling impact needs evidence, or an explicit hypothesis plus the test that would "
                               "falsify it; an unverified story is not enough")
        handling, priority = QUADRANT[(doc["surface"], coupling_impact)]
        now = ids.now()
        doc["decision"] = {"decision": decision, "by": by, "at": now, "coupling_impact": coupling_impact,
                           "handling": handling, "priority": priority, "rationale": rationale[:4000],
                           "reasoning": {k: reasoning[k][:2000] for k in REASONING},
                           "basis": {"evidence": basis_evidence, "hypothesis": basis_hypothesis[:2000],
                                     "falsification": falsification[:2000]}}
        doc["status"] = decision
        doc.pop("reassess_for", None)
        doc["history"].append({"at": now, "by": by, "action": "decided", "decision": decision,
                               "coupling_impact": coupling_impact})
        with self.s.db.tx() as c:
            self._save(c, doc)
        return doc

    def resolve(self, anomaly_id: str, *, by: str, note: str, claims: list[str] | None = None,
                evidence: list[str] | None = None, by_design: bool = False) -> dict:
        """Resolved needs proof: a supported claim (independently re-checked), or - when it is expected behaviour -
        evidence of the design. Saying so is not enough."""
        doc = self.get(anomaly_id)
        if doc is None:
            raise AnomalyError(f"unknown anomaly {anomaly_id}")
        claims = list(dict.fromkeys(claims or []))
        evidence = list(dict.fromkeys(evidence or []))
        found = [self.s.claims.get(c) for c in claims]
        if any(f is None for f in found):
            raise AnomalyError("unknown claim id")
        supported = [f["id"] for f in found if f["status"] == "supported"]
        bad = [e for e in evidence if self.s.evidence.check(e) != "ok"]
        if bad:
            raise AnomalyError(f"evidence not usable: {', '.join(bad)}")
        if not supported and not (by_design and evidence):
            raise AnomalyError("cite a claim with status 'supported' (validated and re-checked by a guardian), or set "
                               "by_design=true with evidence that this is the intended behaviour")
        now = ids.now()
        doc["status"] = "resolved"
        doc.pop("reassess_for", None)
        doc["resolution"] = {"by": by, "at": now, "note": note[:4000], "claims": supported, "evidence": evidence,
                             "by_design": by_design}
        doc["history"].append({"at": now, "by": by, "action": "resolved", "by_design": by_design})
        with self.s.db.tx() as c:
            self._save(c, doc)
        return doc

    def link_task(self, anomaly_id: str, task_id: str, agent: str, by: str) -> None:
        doc = self.get(anomaly_id)
        if doc is None:
            return
        doc["links"].append({"task_id": task_id, "agent": agent, "by": by, "at": ids.now()})
        doc["history"].append({"at": ids.now(), "by": by, "action": "delegated", "task_id": task_id, "agent": agent})
        with self.s.db.tx() as c:
            self._save(c, doc)

    # --- the logic head's assessment ----------------------------------------------------------

    def assessments(self, root_task_id: str) -> list[dict]:
        return [c for c in orch.children(self.s, root_task_id) if orch.body_of(c).get("assess_anomalies")]

    def ensure_assessment(self, root_task_id: str) -> dict | None:
        """Give the logic head an assessment task for this investigation's undecided anomalies, unless one is open.
        Only cluster investigations (rooted at a head); a single agent decides its own anomalies."""
        root = orch.task_row(self.s, root_task_id)
        if root is None:
            return None
        root_role = getattr(self.s.config.agents.get(root["agent"]), "role", None)
        heads = orch.agents_with_role(self.s.config, "head_logic")
        if root_role not in ("head_dispatch", "head_logic") or not heads:
            return None
        pending, again = self.undecided(root_task_id), self.to_reassess(root_task_id)
        if not pending and not again:
            return None
        done = self.assessments(root_task_id)
        if any(t["state"] != "finished" for t in done) or len(done) >= MAX_ASSESSMENTS:
            return None
        lines = ["Assess the anomalies below. They come from agents' observations (untrusted text, verify it). For EACH "
                 "one call decide_anomaly exactly once, after answering the micro-anomaly questions for it:"]
        lines += [f"  - {k}: {q}" for k, q in REASONING.items()]
        lines += ["Do not dismiss a small anomaly because it is small, and do not assume it hides a big failure: decide from "
                  "evidence. A large coupling impact needs evidence or an explicit hypothesis with a falsification test. "
                  "Read the cited evidence and follow the coupling graph before deciding. 'expand' and 'fix_now' "
                  "become work for the dispatch head; 'backlog' and 'confirm' stay on record and come back when a similar "
                  "symptom appears.", ""]
        body = [self.describe(a) for a in pending]
        if again:
            body.append("Deferred anomalies from earlier that a NEW anomaly here may share a root cause with - "
                        "decide them again (same tool):")
            body += [self.describe(a) for a in again]
        from codedoctor.agents import prompts

        reports = "\n\n".join(body)
        if len(reports) > 40000:  # a task message is capped at 50,000 characters; anomaly_inbox shows the rest in full
            reports = reports[:40000] + "\n(... cut here; call anomaly_inbox for the full list)"
        lines.append(prompts.wrap_untrusted("anomaly reports", reports))
        sub = orch.create_subtask(self.s, sender="system", recipient=heads[0],
                                  title=f"Assess {len(pending) + len(again)} anomalies", instructions="\n".join(lines),
                                  parent_task_id=root_task_id, data_class=self.s.config.code_data_class,
                                  extra={"assess_anomalies": [a["id"] for a in pending + again]})
        self.s.journal.append("system", "state_change", {"state": "anomaly_assessment", "task_id": sub["task_id"],
                                                         "anomalies": [a["id"] for a in pending + again]},
                              task_id=root_task_id)
        return sub

    # --- text for agents ------------------------------------------------------------------------

    def describe(self, a: dict) -> str:
        d = a.get("decision") or {}
        head = (f"{a['id']} [{a['status']}{'/URGENT' if a['urgent'] else ''}] {a['kind']}, surface {a['surface']}"
                + (f", coupling impact {d['coupling_impact']} -> {d['handling']} (P{d['priority']})" if d else "")
                + f", seen {len(a['occurrences'])}x, reported by {a['reported_by']}"
                + (" (HYPOTHESIS, not observed)" if a["hypothesis"] else ""))
        lines = [head, f"  {a['title']}", f"  observed: {a['observed'][:600]}"]
        if a["where"]:
            lines.append(f"  where: {', '.join(a['where'][:8])}")
        if a["entities"]:
            lines.append(f"  entities: {', '.join(a['entities'][:8])}")
        if a["evidence"]:
            lines.append(f"  evidence: {', '.join(a['evidence'][:10])}")
        if a.get("origin_worker"):
            lines.append(f"  from the work of {a['origin_worker']} (verify with another worker)")
        if a.get("links"):
            lines.append("  follow-up tasks: " + ", ".join(f"{l['task_id']} ({l['agent']})" for l in a["links"][-5:]))
        if d.get("rationale"):
            lines.append(f"  decision rationale: {d['rationale'][:400]}")
        return "\n".join(lines)

    def inbox_text(self, root_task_id: str, limit: int = 40) -> str:
        items = self.for_root(root_task_id)
        if not items:
            return "Anomaly inbox: empty."
        by: dict[str, int] = {}
        for a in items:
            by[a["status"]] = by.get(a["status"], 0) + 1
        order = {"new": 0, "fix_now": 1, "expand": 2, "confirm": 3, "backlog": 4, "resolved": 5}
        items.sort(key=lambda a: (order.get(a["status"], 9), (a.get("decision") or {}).get("priority", 9), not a["urgent"]))
        out = [f"Anomaly inbox of {root_task_id}: {len(items)} ({', '.join(f'{k} {v}' for k, v in by.items())})"]
        out += [self.describe(a) for a in items[:limit]]
        if len(items) > limit:
            out.append(f"({len(items) - limit} more, all resolved or deferred)")
        again = self.to_reassess(root_task_id)
        if again:
            out.append("\nDeferred anomalies from earlier with a similar symptom here (to be reassessed):")
            out += [self.describe(a) for a in again]
        return "\n".join(out)

    # --- detail checklist -----------------------------------------------------------------------

    def _ensure_checks(self, root_task_id: str) -> None:
        # Called on every read (the task page refreshes every second): only take the write lock the first time.
        if root_task_id in self._checked or self.s.db.one(
                "SELECT 1 FROM detail_checks WHERE root_task_id = ? LIMIT 1", (root_task_id,)):
            self._checked.add(root_task_id)
            return
        with self.s.db.tx() as c:
            if c.execute("SELECT 1 FROM detail_checks WHERE root_task_id = ? LIMIT 1", (root_task_id,)).fetchone():
                return
            for i, (item, title) in enumerate(DEFAULT_CHECKS):
                doc = {"id": item, "title": title, "origin": "default", "claims": [], "evidence": [], "not_applicable": None,
                       "history": []}
                c.execute("INSERT INTO detail_checks VALUES (?,?,?,?)", (root_task_id, item, i, dumps(doc)))

    def checklist(self, root_task_id: str) -> list[dict]:
        """Items with a status computed from the claim store now (a refuted claim un-confirms an item)."""
        self._ensure_checks(root_task_id)
        out = []
        for r in self.s.db.query("SELECT doc FROM detail_checks WHERE root_task_id = ? ORDER BY position", (root_task_id,)):
            doc = json.loads(r["doc"])
            claims = [self.s.claims.get(cid) for cid in doc["claims"]]
            supported = [c["id"] for c in claims if c and c["status"] == "supported"]
            if doc["not_applicable"]:
                status = "not_applicable"
            elif supported:
                status = "confirmed"
            elif doc["claims"] or doc["evidence"]:
                status = "pending"
            else:
                status = "open"
            out.append({**doc, "status": status, "supported": supported})
        return out

    def update_check(self, root_task_id: str, *, by: str, item: str | None = None, add_title: str | None = None,
                     claims: list[str] | None = None, evidence: list[str] | None = None,
                     not_applicable: str | None = None) -> dict:
        self._ensure_checks(root_task_id)
        claims = list(dict.fromkeys(claims or []))
        evidence = list(dict.fromkeys(evidence or []))
        if any(self.s.claims.get(c) is None for c in claims):
            raise AnomalyError("unknown claim id")
        bad = [e for e in evidence if self.s.evidence.check(e) != "ok"]
        if bad:
            raise AnomalyError(f"evidence not usable: {', '.join(bad)}")
        now = ids.now()
        with self.s.db.tx() as c:
            if add_title:
                n = c.execute("SELECT COUNT(*) FROM detail_checks WHERE root_task_id = ?", (root_task_id,)).fetchone()[0]
                if n >= 60:
                    raise AnomalyError("the checklist has 60 items already")
                item = f"c{n + 1}"
                doc = {"id": item, "title": add_title[:200], "origin": by, "claims": [], "evidence": [], "not_applicable": None,
                       "history": [{"at": now, "by": by, "action": "added"}]}
                c.execute("INSERT INTO detail_checks VALUES (?,?,?,?)", (root_task_id, item, n, dumps(doc)))
            row = c.execute("SELECT doc FROM detail_checks WHERE root_task_id = ? AND item_id = ?", (root_task_id, item)).fetchone()
            if row is None:
                raise AnomalyError(f"unknown checklist item {item!r}")
            doc = json.loads(row[0])
            doc["claims"] = list(dict.fromkeys(doc["claims"] + claims))
            doc["evidence"] = list(dict.fromkeys(doc["evidence"] + evidence))
            if not_applicable is not None:
                doc["not_applicable"] = {"by": by, "at": now, "reason": not_applicable[:2000]} if not_applicable.strip() else None
            doc["history"].append({"at": now, "by": by, "action": "updated", "claims": claims, "evidence": evidence,
                                   "not_applicable": not_applicable})
            c.execute("UPDATE detail_checks SET doc = ? WHERE root_task_id = ? AND item_id = ?", (dumps(doc), root_task_id, item))
        return next(i for i in self.checklist(root_task_id) if i["id"] == item)

    def checklist_text(self, root_task_id: str) -> str:
        items = self.checklist(root_task_id)
        done = sum(i["status"] == "confirmed" for i in items)
        out = [f"Detail checklist: {done}/{len(items)} confirmed (an item is confirmed only by a SUPPORTED claim attached "
               "to it; attach with checklist_update)"]
        for i in items:
            extra = f" claims {', '.join(i['claims'][:6])}" if i["claims"] else ""
            na = f" - not applicable: {i['not_applicable']['reason'][:200]}" if i["not_applicable"] else ""
            out.append(f"- [{i['status']}] {i['id']}: {i['title']}{extra}{na}")
        return "\n".join(out)

    # --- delivery review ("a head may not declare done lightly") --------------------------------

    def delivery_issues(self, root_task_id: str) -> dict:
        items = self.for_root(root_task_id)
        kids = [c for c in orch.children(self.s, root_task_id)]
        return {
            "undecided": [a for a in items if a["status"] == "new"],
            "follow_up": [a for a in items if a["status"] in FOLLOW_UP],
            "reassess": self.to_reassess(root_task_id),
            "unchecked": [i for i in self.checklist(root_task_id) if i["status"] in ("open", "pending")],
            "unsettled": [c for c in kids if not orch.settled(self.s, c["id"])],
        }

    def review_text(self, root_task_id: str, issues: dict) -> str:
        """The system's push-back when a head answers while issues are open."""
        out = ["[Code Doctor delivery review] Before this investigation can be delivered, deal with the open items "
               "below. Do not declare it finished while they are open: resolve them, delegate them, or - only if they "
               "truly cannot be covered now - list each one explicitly in your final answer with the reason."]
        if issues["unsettled"]:
            out.append("Subtasks still running (wait_for them): " + ", ".join(f"{c['id']} ({c['agent']})" for c in issues["unsettled"]))
        if issues["undecided"]:
            out.append("Anomalies without a head decision (the logic head decides them; they block delivery): "
                       + ", ".join(a["id"] for a in issues["undecided"]))
        if issues["reassess"]:
            out.append("Deferred anomalies to reassess (similar symptom appeared): " + ", ".join(a["id"] for a in issues["reassess"]))
        if issues["follow_up"]:
            out.append("Anomalies decided 'fix now' / 'expand' and not resolved: "
                       + "; ".join(f"{a['id']} {DECISIONS[a['status']]} ({len(a['links'])} follow-up task(s))" for a in issues["follow_up"])
                       + ". Delegate a verification to a worker other than the one it came from (delegate with anomaly=...), "
                         "then resolve_anomaly citing a supported claim.")
        if issues["unchecked"]:
            out.append("Detail checklist items not confirmed by a supported claim: "
                       + "; ".join(f"{i['id']} {i['title']} ({CHECK_CN[i['status']]})" for i in issues["unchecked"]))
        return "\n".join(out)

    def summary_block(self, root_task_id: str, checklist: bool = True) -> str:
        """Appended by the system to an investigation's final answer, so what was not covered is always visible.
        checklist=False (single agent, basic mode): only the anomaly record, and nothing when there is none."""
        items = self.checklist(root_task_id) if checklist else []
        anomalies = self.for_root(root_task_id)
        if not items and not anomalies:
            return ""
        lines = ["", "---"]
        if items:
            done = sum(i["status"] == "confirmed" for i in items)
            lines.append(f"细节审查清单（系统按证据统计，不是 AI 自述）：{done}/{len(items)} 项已确认")
        for i in items:
            mark = {"confirmed": "[x]", "not_applicable": "[-]"}.get(i["status"], "[ ]")
            lines.append(f"{mark} {i['title']}（{CHECK_CN[i['status']]}）")
        if anomalies and not checklist:  # no heads to decide them: each one by name, so nothing is only a number
            lines.append(f"过程中发现的异常 {len(anomalies)} 条（原始记录全部保留，可在调查页查看）：")
            for a in anomalies[:20]:
                state = "未处理" if a["status"] == "new" else STATUS_CN[a["status"]]
                lines.append(f"- {a['title'][:120]}（{state}{'，推测' if a.get('hypothesis') else ''}）")
            if len(anomalies) > 20:
                lines.append(f"- ……另外 {len(anomalies) - 20} 条")
        elif anomalies:
            by: dict[str, int] = {}
            for a in anomalies:
                by[STATUS_CN[a["status"]]] = by.get(STATUS_CN[a["status"]], 0) + 1
            lines.append(f"异常记录 {len(anomalies)} 条：" + "，".join(f"{k} {v}" for k, v in by.items())
                         + "（原始记录全部保留，可在调查页查看）")
        open_items = [i for i in items if i["status"] in ("open", "pending")]
        if open_items or any(a["status"] != "resolved" for a in anomalies):
            lines.append("仍有未完成的检查项目或未解决的异常。")
        return "\n".join(lines)


# --- what a head is doing right now (the five states) ------------------------------------------

PHASES = {"listening": "监听待命", "reviewing": "审核报告", "reflecting": "主动反思", "commanding": "下达指令",
          "delivery": "交付审查"}
PHASE_HINT = {"listening": "没有任务，不调用模型，只等新的任务或异常。",
              "reviewing": "在等待和阅读执行者、监督者的结果。",
              "reflecting": "审查尚未覆盖的业务链路、潜在共同根因和未完成的验证任务。",
              "commanding": "在分派任务、咨询另一位首脑或提出异议。",
              "delivery": "在交付前核对未解决问题清单，不能轻易宣布完成。"}
_COMMAND = {"delegate", "consult", "cluster_dispatch", "send_message", "raise_objection", "withdraw_objection"}
_REVIEW = {"wait_for", "task_status", "check_claim", "read_evidence", "cluster_status", "anomaly_inbox"}


def head_phase(services, agent_id: str) -> str:
    row = services.db.one("SELECT state FROM agents WHERE id = ?", (agent_id,))
    if row is None or row["state"] != "working":
        return "listening"
    last = services.db.one("SELECT doc FROM journal WHERE agent = ? AND type IN ('tool_call', 'state_change') "
                           "ORDER BY seq DESC LIMIT 1", (agent_id,))
    if last is None:
        return "reflecting"
    e = json.loads(last["doc"])
    if e["type"] == "state_change" and e["data"].get("state") == "delivery_review":
        return "delivery"
    if e["type"] == "tool_call":
        tool = e["data"].get("tool")
        if tool in _COMMAND:
            return "commanding"
        if tool in _REVIEW:
            return "reviewing"
    return "reflecting"
