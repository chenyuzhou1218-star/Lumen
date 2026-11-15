"""Native desktop window (tkinter): give the agent a task, watch its progress, read the report.

The window and the background service run in ONE process: the service's event
loop runs in a background thread and the window calls it directly - no browser,
no HTTP. Closing the window stops the service; interrupted tasks can be resumed
next time ("继续执行").

    codedoctor gui --config local/codedoctor.toml
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from codedoctor import config as config_mod
from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.agents.effects import describe
from codedoctor.backend import Backend  # noqa: F401  (re-exported for callers)
from codedoctor.store.lock import AlreadyRunning

FONT = ("Microsoft YaHei UI", 10)
MONO = ("Consolas", 10)
REFRESH_MS = 1000

STATE_CN = {"queued": "排队中", "running": "运行中", "finished": "已结束"}
OUTCOME_CN = {"done": "完成", "failed": "失败", "blocked": "被拦下", "budget_exhausted": "预算用完",
              "stalled": "无进展已停止", "cancelled": "已取消", "interrupted": "中断"}
AGENT_CN = {"idle": "空闲", "working": "工作中", "paused": "已暂停", "stopped": "已停止"}
TOOL_CN = {"list_dir": "查看目录", "read_file": "读取文件", "search_text": "搜索文本", "run_command": "执行命令",
           "read_evidence": "读取证据", "remember": "写入记忆", "recall": "检索记忆", "submit_claim": "提交结论",
           "check_claim": "检查结论", "withdraw_claim": "撤回结论", "review_claim": "审查结论", "send_message": "发送消息"}
CLAIM_CN = {"proposed": "待验证", "supported": "成立", "refuted": "被推翻", "needs_revalidation": "需要重新验证",
            "superseded": "已被取代", "withdrawn": "已撤回"}
RESUMABLE = {"interrupted", "blocked", "budget_exhausted", "stalled"}
RISK_CN = {"shared_state_multi_writer": "多个入口写同一数据", "retry_path_to_write": "重试/重连会重复写入",
           "multi_write_without_transaction": "多处写入没有事务", "silent_noop_path": "静默失败（不报错直接返回）",
           "event_without_listener": "事件发出但无人监听", "listener_without_event": "监听的事件无人发出",
           "client_route_without_handler": "调用了后端不存在的接口"}
SEVERITY_CN = {"high": "高", "medium": "中", "low": "低"}


def local_time(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")


def task_status(row: dict) -> str:
    if row["state"] == "finished":
        return OUTCOME_CN.get(row["outcome"], row["outcome"] or "已结束")
    return STATE_CN.get(row["state"], row["state"])


class App:
    def __init__(self, root: tk.Tk, cfg, backend: Backend):
        self.root, self.cfg, self.b = root, cfg, backend
        self.d = backend.daemon
        self.selected: str | None = None
        self.last_seq = 0
        self.entries: dict[str, dict] = {}
        self.task_rows: dict[str, dict] = {}
        self._build()
        self.refresh()

    # --- layout ------------------------------------------------------------------------

    def _build(self) -> None:
        r = self.root
        scale = float(r.tk.call("tk", "scaling")) / 1.3333  # 1.0 at 100% Windows scaling, 1.5 at 150%
        px = lambda n: int(n * scale)  # noqa: E731
        r.title(f"Lumen — {self.cfg.name}")
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        r.geometry(f"{int(sw * 0.8)}x{int(sh * 0.8)}+{int(sw * 0.1)}+{int(sh * 0.06)}")
        r.minsize(px(900), px(560))
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure(".", font=FONT)
        style.configure("Treeview", rowheight=px(24), font=FONT)
        style.configure("Treeview.Heading", font=(FONT[0], 10, "bold"))
        style.configure("Title.TLabel", font=(FONT[0], 13, "bold"))
        style.configure("Warn.TLabel", foreground="#b3261e")

        top = ttk.Frame(r, padding=(10, 8))
        top.pack(fill="x")
        root_text = str(self.cfg.root)
        if len(root_text) > 60:
            root_text = root_text[:25] + "…" + root_text[-32:]
        ttk.Label(top, text=f"检查项目：{self.cfg.name}", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text=f"  {root_text}").pack(side="left")
        # One line per run of agents; wraps instead of running off the window when a cluster has many agents.
        self.agent_label = ttk.Label(r, text="", padding=(10, 0), wraplength=int(r.winfo_screenwidth() * 0.75))
        self.agent_label.pack(fill="x")
        missing = [e.api_key_env for e in self.cfg.endpoints.values() if e.api_key_env and not os.environ.get(e.api_key_env)]
        if missing:
            ttk.Label(r, style="Warn.TLabel", padding=(10, 0),
                      text=f"未设置密钥环境变量：{', '.join(missing)}。Agent 调用该模型时会停下并提示。"
                           f"设置方法：在命令行运行  setx {missing[0]} 你的密钥 ，然后重新打开本程序。").pack(fill="x")

        panes = ttk.PanedWindow(r, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        left = ttk.Frame(panes)
        panes.add(left, weight=1)
        new = ttk.LabelFrame(left, text="新任务", padding=8)
        new.pack(fill="x")
        row = ttk.Frame(new)
        row.pack(fill="x")
        ttk.Label(row, text="Agent：").pack(side="left")
        self.agent_var = tk.StringVar(value=next(iter(self.cfg.agents)))
        ttk.Combobox(row, textvariable=self.agent_var, values=list(self.cfg.agents), state="readonly", width=16).pack(side="left")
        ttk.Label(new, text="标题（可不填）：").pack(anchor="w", pady=(6, 0))
        self.title_entry = ttk.Entry(new)
        self.title_entry.pack(fill="x")
        ttk.Label(new, text="要查的问题：").pack(anchor="w", pady=(6, 0))
        self.instr = tk.Text(new, height=7, wrap="word", font=FONT, undo=True)
        self.instr.pack(fill="x")
        self.instr.bind("<Control-Return>", lambda e: (self.submit(), "break")[1])
        ttk.Button(new, text="开始调查（Ctrl+Enter）", command=self.submit).pack(anchor="e", pady=(6, 0))

        lst = ttk.LabelFrame(left, text="任务列表", padding=8)
        lst.pack(fill="both", expand=True, pady=(8, 0))
        self.tasks = ttk.Treeview(lst, columns=("time", "title", "status"), show="tree headings", selectmode="browse")
        self.tasks.column("#0", width=px(22), stretch=False)
        for col, text, width in (("time", "时间", 80), ("title", "标题", 200), ("status", "状态", 100)):
            self.tasks.heading(col, text=text)
            self.tasks.column(col, width=px(width), minwidth=px(width) if col != "title" else px(80), stretch=(col == "title"))
        self.tasks.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lst, command=self.tasks.yview)
        sb.pack(side="right", fill="y")
        self.tasks.configure(yscrollcommand=sb.set)
        self.tasks.bind("<<TreeviewSelect>>", lambda e: self.select(self.tasks.selection()[0] if self.tasks.selection() else None))

        right = ttk.Frame(panes)
        panes.add(right, weight=3)
        def place_sash() -> None:
            width = panes.winfo_width()
            if width < px(600):  # not laid out yet
                r.after(50, place_sash)
                return
            panes.sashpos(0, max(px(380), int(width * 0.32)))

        r.after(50, place_sash)
        head = ttk.Frame(right)
        head.pack(fill="x")
        self.head_title = ttk.Label(head, text="← 在左边新建任务，或选中一个任务", style="Title.TLabel")
        self.head_title.pack(side="left")
        self.resume_btn = ttk.Button(head, text="继续执行", command=lambda: self.control("resume_task"))
        self.cancel_btn = ttk.Button(head, text="取消任务", command=lambda: self.control("cancel_task"))
        self.resume_btn.pack(side="right")
        self.cancel_btn.pack(side="right", padx=6)
        self.head_info = ttk.Label(right, text="")
        self.head_info.pack(fill="x", pady=(2, 6))

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)
        self.nb = nb
        prog = ttk.Frame(nb, padding=4)
        nb.add(prog, text="进度")
        split = ttk.PanedWindow(prog, orient="vertical")
        split.pack(fill="both", expand=True)
        tl_frame = ttk.Frame(split)
        split.add(tl_frame, weight=3)
        self.timeline = ttk.Treeview(tl_frame, columns=("time", "event", "detail"), show="headings", selectmode="browse")
        for col, text, width in (("time", "时间", 80), ("event", "事件", 220), ("detail", "详情", 500)):
            self.timeline.heading(col, text=text, anchor="w")
            self.timeline.column(col, width=px(width), minwidth=px(width) if col == "time" else px(60), stretch=(col == "detail"))
        self.timeline.tag_configure("bad", foreground="#b3261e")
        self.timeline.tag_configure("good", foreground="#146c2e")
        self.timeline.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(tl_frame, command=self.timeline.yview)
        sb2.pack(side="right", fill="y")
        self.timeline.configure(yscrollcommand=sb2.set)
        self.timeline.bind("<<TreeviewSelect>>", lambda e: self.show_entry())
        det_frame = ttk.LabelFrame(split, text="选中事件的完整内容", padding=4)
        split.add(det_frame, weight=2)
        self.detail = self._readonly_text(det_frame, MONO)

        rep = ttk.Frame(nb, padding=4)
        nb.add(rep, text="报告")
        self.report = self._readonly_text(rep, FONT)

        gtab = ttk.Frame(nb, padding=4)
        nb.add(gtab, text="耦合图谱")
        bar = ttk.Frame(gtab)
        bar.pack(fill="x")
        self.graph_btn = ttk.Button(bar, text="构建 / 刷新图谱", command=self.rebuild_graph)
        self.graph_btn.pack(side="left")
        ttk.Label(bar, text="   查找：").pack(side="left")
        self.graph_query = ttk.Entry(bar, width=36)
        self.graph_query.pack(side="left")
        self.graph_query.bind("<Return>", lambda e: self.graph_lookup("find"))
        ttk.Button(bar, text="查找", command=lambda: self.graph_lookup("find")).pack(side="left", padx=4)
        ttk.Button(bar, text="影响范围", command=lambda: self.graph_lookup("impact")).pack(side="left")
        ttk.Button(bar, text="直接关系", command=lambda: self.graph_lookup("neighbors")).pack(side="left", padx=4)
        ttk.Button(bar, text="风险线索", command=self.show_graph_overview).pack(side="left")
        self.graph_text = self._readonly_text(gtab, MONO)
        self._graph_busy = False
        r.after(300, self.show_graph_overview)

        self.status = ttk.Label(r, padding=(10, 4), text="后台已在本窗口内运行 · 关闭窗口即停止后台（运行中的任务下次可以继续执行）")
        self.status.pack(fill="x")
        r.protocol("WM_DELETE_WINDOW", self.on_close)

    @staticmethod
    def _readonly_text(parent, font) -> tk.Text:
        t = tk.Text(parent, wrap="word", font=font, state="disabled", padx=6, pady=6)
        sb = ttk.Scrollbar(parent, command=t.yview)
        sb.pack(side="right", fill="y")
        t.configure(yscrollcommand=sb.set)
        t.pack(fill="both", expand=True)
        return t

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    # --- actions -----------------------------------------------------------------------

    def submit(self) -> None:
        text = self.instr.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Lumen", "请先写下要查的问题。")
            return
        title = self.title_entry.get().strip() or text.splitlines()[0][:60]
        try:
            sub = self.b.run(self.d.submit_task, self.agent_var.get(), title, text)
        except Exception as e:
            messagebox.showerror("提交失败", str(e))
            return
        self.instr.delete("1.0", "end")
        self.title_entry.delete(0, "end")
        self.refresh_tasks()
        self.tasks.selection_set(sub["task_id"])
        self.tasks.see(sub["task_id"])

    def control(self, command: str) -> None:
        if not self.selected:
            return
        row = self.task_rows.get(self.selected)
        if command == "cancel_task" and not messagebox.askyesno("取消任务", "确定取消这个任务？已经完成的步骤会保留。"):
            return
        try:
            self.b.run(self.d.control, row["agent"], command, task_id=self.selected)
        except Exception as e:
            messagebox.showerror("操作失败", str(e))

    def select(self, task_id: str | None) -> None:
        self.selected = task_id
        self.last_seq = 0
        self.entries.clear()
        self.timeline.delete(*self.timeline.get_children())
        self._set_text(self.detail, "")
        self._set_text(self.report, "")
        self.refresh_selected()

    # --- coupling graph tab -----------------------------------------------------------------

    def rebuild_graph(self) -> None:
        if self._graph_busy:
            return
        self._graph_busy = True
        self.graph_btn.state(["disabled"])
        self._set_text(self.graph_text, "正在分析项目代码，构建耦合图谱……（几百个文件通常需要几秒到几十秒）")
        result: dict = {}

        def work():
            try:
                result["meta"] = self.d.s.graph.build()
            except Exception as e:  # shown in the tab
                result["error"] = f"{type(e).__name__}: {e}"

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not result:
                self.root.after(300, poll)
                return
            self._graph_busy = False
            self.graph_btn.state(["!disabled"])
            if "error" in result:
                self._set_text(self.graph_text, "构建失败：" + result["error"])
            else:
                self.show_graph_overview()

        poll()

    def show_graph_overview(self) -> None:
        gs = self.d.s.graph
        meta = gs.meta()
        if not meta:
            self._set_text(self.graph_text, "还没有耦合图谱。点击“构建 / 刷新图谱”分析项目代码。\n"
                                            "（Agent 第一次用到图谱时也会自动构建。）")
            return
        st = meta["stats"]
        counts = gs.risk_counts()
        lines = [
            f"项目：{self.cfg.name}    代码版本：{meta['code_version'][:20]}…    构建时间：{local_time(meta['built_at'])}    用时 {meta['seconds']} 秒",
            f"文件 {meta['files']} 个（{meta['languages']}），解析失败 {len(meta.get('parse_errors', {}))} 个",
            f"节点 {st['nodes']} 个：{st['node_types']}",
            f"关系 {st['edges']} 条：{st['edge_provenance']}（static = 从代码静态分析得到）",
            "",
            "风险线索统计（不是确认的 Bug，需要 Agent 验证）：",
        ]
        by_pattern: dict = {}
        for key, n in counts.items():
            pattern, sev = key.split("/")
            by_pattern.setdefault(pattern, {})[sev] = n
        for pattern, sev in sorted(by_pattern.items()):
            lines.append(f"  {RISK_CN.get(pattern, pattern)}：" + "，".join(f"{SEVERITY_CN[s]} {sev[s]}" for s in ("high", "medium", "low") if s in sev))
        lines += ["", "最重要的风险线索："]
        for r in gs.risks(limit=25, min_severity="medium"):
            locs = "，".join(f"{l['path']}:{l['line']}" for l in r["locations"][:3])
            lines += [f"", f"[{SEVERITY_CN[r['severity']]}] {RISK_CN.get(r['pattern'], r['pattern'])}",
                      f"    {r['explanation']}", f"    位置：{locs}", f"    验证方法：{r['how_to_verify']}"]
        self._set_text(self.graph_text, "\n".join(lines))

    def graph_lookup(self, mode: str) -> None:
        text = self.graph_query.get().strip()
        if not text:
            return
        if not self.d.s.graph.meta():
            self._set_text(self.graph_text, "请先构建耦合图谱。")
            return
        g = self.d.s.graph.graph()
        if mode == "find":
            hits = g.find(text, 60)
            out = [f"{n.type:<8} {n.id}" + (f"   @ {n.path}:{n.line}" if n.path else "") for n in hits] or ["没有找到"]
            self._set_text(self.graph_text, f"查找“{text}”：{len(hits)} 个\n\n" + "\n".join(out))
            return
        node = g.resolve(text)
        if node is None:
            self._set_text(self.graph_text, f"没有找到“{text}”")
            return
        loc = f"   @ {node.path}:{node.line}" if node.path else ""
        if mode == "neighbors":
            out = [f"{node.id}{loc}", "", f"指向外部（{len(g.out.get(node.id, []))}）："]
            out += [f"  -{e.rel}-> {e.dst}   ({e.provenance}{', ' + e.resolution if e.resolution else ''})"
                    f"{'   @ ' + str(e.path) + ':' + str(e.line) if e.path else ''}" for e in g.out.get(node.id, [])[:200]]
            out += ["", f"来自外部（{len(g.inc.get(node.id, []))}）："]
            out += [f"  <-{e.rel}- {e.src}   ({e.provenance}{', ' + e.resolution if e.resolution else ''})"
                    f"{'   @ ' + str(e.path) + ':' + str(e.line) if e.path else ''}" for e in g.inc.get(node.id, [])[:200]]
            self._set_text(self.graph_text, "\n".join(out))
            return
        imp = g.impact(node.id, 5)
        out = [f"{node.id}{loc}", "（不沿“同名不确定”的关系扩散）"]
        for title, key in (("它会影响（改动它可能波及这些）", "affects"), ("影响它的（这些出问题会波及它）", "affected_by")):
            items = sorted((d, ent) for ent, (d, _) in imp[key].items() if ent != node.id and not ent.startswith("ent:file:"))
            out += ["", f"{title}：{len(items)} 个"]
            out += [f"  距离 {d}  {ent}" for d, ent in items[:150]]
        self._set_text(self.graph_text, "\n".join(out))

    def on_close(self) -> None:
        running = [t for t in self.task_rows.values() if t["state"] != "finished"]
        if running and not messagebox.askyesno(
                "关闭 Lumen", f"还有 {len(running)} 个任务没有结束。关闭会中断它们（下次打开后可以点“继续执行”）。确定关闭？"):
            return
        self.status.configure(text="正在停止后台……")
        self.root.update_idletasks()
        try:
            self.b.close()
        finally:
            self.root.destroy()

    # --- refresh -----------------------------------------------------------------------

    def refresh(self) -> None:
        try:
            states = self.d.agent_states()
            self.agent_label.configure(text="    ".join(
                f"{a['id']}（{a['model']}）：{AGENT_CN.get(a['state'], a['state'])}" for a in states))
            self.refresh_tasks()
            self.refresh_selected()
        except Exception as e:  # never let a refresh error kill the window
            self.status.configure(text=f"刷新出错：{type(e).__name__}: {e}")
        self.root.after(REFRESH_MS, self.refresh)

    def refresh_tasks(self) -> None:
        """Task tree: a user task with its consult / worker / guardian review subtasks under it."""
        rows = self.d.recent_tasks(300)
        for t in sorted(rows, key=lambda r: r["created_at"]):  # parents before children
            label = t["title"] if not t.get("parent_task_id") else f"[{t['agent']}] {t['title']}"
            values = (local_time(t["created_at"]), label, task_status(t))
            if self.tasks.exists(t["id"]):
                if self.task_rows.get(t["id"]) != t:
                    self.tasks.item(t["id"], values=values)
            else:
                parent = t.get("parent_task_id")
                if parent and self.tasks.exists(parent):
                    self.tasks.insert(parent, "end", iid=t["id"], values=values)
                    self.tasks.item(parent, open=True)
                else:
                    self.tasks.insert("", 0, iid=t["id"], values=values)
            self.task_rows[t["id"]] = t

    def refresh_selected(self) -> None:
        if not self.selected:
            self.cancel_btn.state(["disabled"])
            self.resume_btn.state(["disabled"])
            return
        task = self.d.task(self.selected)
        if task is None:
            return
        for e in self.d.s.journal.read(task_id=self.selected, after_seq=self.last_seq, limit=2000):
            self.last_seq = e["seq"]
            self.entries[e["id"]] = e
            event, detail, tag = self.describe_entry(e)
            self.timeline.insert("", "end", iid=e["id"], values=(local_time(e["at"]), event, detail), tags=(tag,) if tag else ())
            self.timeline.see(e["id"])

        usage = task["usage"] or {}
        if task["state"] != "finished":
            start = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")).timestamp()
            elapsed = int(time.time() - start)
        else:
            elapsed = int((usage.get("wall_ms") or 0) / 1000)
        steps = sum(1 for e in self.entries.values() if e["type"] == "model_response")
        self.head_title.configure(text=task["title"])
        self.head_info.configure(text=(
            f"状态：{task_status(task)}    Agent：{task['agent']}    已进行 {steps} 步    用时 {elapsed // 60} 分 {elapsed % 60} 秒"
            + (f"    token：输入 {usage.get('input_tokens', 0)} / 输出 {usage.get('output_tokens', 0)}" if usage else "")))
        self.cancel_btn.state(["!disabled"] if task["state"] != "finished" else ["disabled"])
        self.resume_btn.state(["!disabled"] if task["state"] == "finished" and task["outcome"] in RESUMABLE else ["disabled"])
        self._set_report(task)

    def _subtree_claims(self, task_id: str) -> list[tuple[str, dict]]:
        out, stack = [], [task_id]
        while stack:
            tid = stack.pop()
            for c in self.d.s.claims.by_task(tid):
                out.append((tid, c))
            stack.extend(ch["id"] for ch in orch.children(self.d.s, tid))
        return out

    def _set_report(self, task: dict) -> None:
        # Subtasks share the thread: only this task's own report and escalations belong here.
        own = [m for m in task["messages"] if m["body"].get("task_id") == task["id"]]
        reports = [m for m in own if m["kind"] == "report"]
        escalations = [m for m in own if m["kind"] == "escalation"]
        lines = []
        if not reports:
            lines.append("还没有报告。任务结束后，最终回答会显示在这里。")
        for m in reports:
            b = m["body"]
            lines += [f"【{OUTCOME_CN.get(b['outcome'], b['outcome'])}】 {local_time(m['created_at'])}", "", b["summary"], ""]
            u = b.get("usage", {})
            lines.append(f"用量：{u.get('steps', 0)} 步，模型调用 {u.get('model_calls', 0)} 次，"
                         f"token 输入 {u.get('input_tokens', 0)} / 输出 {u.get('output_tokens', 0)}，用时 {(u.get('wall_ms') or 0) // 1000} 秒")
            lines.append("")
        if escalations:
            lines.append("—— 需要你处理的问题 ——")
            lines += [f"[{m['body']['reason']}] {m['body']['detail']}" for m in escalations]
            lines.append("")
        evidence = sorted({ev for m in reports for ev in m["body"].get("evidence", [])})
        if evidence:
            lines.append(f"—— 证据（{len(evidence)} 条，可在“进度”里查看原文）——")
            lines += evidence
            lines.append("")
        claims = self._subtree_claims(task["id"])
        if claims:
            lines.append("—— 结论（主张，含所有子任务）——  只有“成立”是经过独立复查的事实")
            for _, c in claims:
                reviews = self.d.s.claims.reviews(c["id"])
                rv = "；".join(f"{r['reviewer']} {r['verdict']}" for r in reviews) or "尚无独立复查"
                lines.append(f"[{CLAIM_CN.get(c['status'], c['status'])} · {c['evidence_level']}] {c['statement']['text']}")
                lines.append(f"    提出者 {c['author']['id']} · 复查：{rv} · {c['id']}")
            lines.append("")
        if task["side_effects"]:
            lines.append("—— 副作用账本 ——")
            lines.append(describe(task["side_effects"]))
        text = "\n".join(lines)
        if self.report.get("1.0", "end-1c") != text:
            self._set_text(self.report, text)

    def describe_entry(self, e: dict) -> tuple[str, str, str | None]:
        t, d = e["type"], e["data"]
        model = e.get("model", {}).get("model", "")
        if t == "message_in":
            kinds = {"task": "任务", "question": "问题", "control": "控制命令", "report": "子任务报告", "answer": "回答",
                     "review": "审查结果", "escalation": "上报"}
            return "收到" + kinds.get(d.get("kind"), d.get("kind", "")), f"来自 {d.get('from', '')}", None
        if t == "model_request":
            return f"请求模型 {model}", f"上下文 {d.get('messages', '?')} 条消息", None
        if t == "model_response":
            n = d.get("tool_calls", 0)
            what = f"模型决定调用 {n} 个工具" if n else "模型给出最终回答"
            return what, f"token 输入 {d.get('input_tokens', 0)} / 输出 {d.get('output_tokens', 0)}", "good" if not n else None
        if t == "model_error":
            return "模型出错", d.get("error", ""), "bad"
        if t == "model_switch":
            return "切换到备用模型（按你的配置）", f"{d.get('to')}  原因：{d.get('after')}", "bad"
        if t == "tool_call":
            args = json.dumps(d.get("arguments", {}), ensure_ascii=False)
            return f"调用工具：{TOOL_CN.get(d.get('tool'), d.get('tool'))}", args[:300], None
        if t == "tool_result":
            if d.get("truncated"):
                return "工具结果", "（内容较长，点击查看）", None
            ok = d.get("ok")
            ev = "，".join(d.get("evidence", []))
            return ("工具结果：成功" if ok else "工具结果：失败"), (f"证据 {ev}" if ev else "点击查看结果"), None if ok else "bad"
        if t == "budget_stop":
            return "预算用完，停止", json.dumps(d, ensure_ascii=False), "bad"
        if t == "stall_stop":
            return "连续没有新进展，停止", f"{d.get('steps_without_progress')} 步", "bad"
        if t == "state_change":
            return f"状态：{d.get('state')}", d.get("reason", ""), "bad" if d.get("state") in ("error", "interrupted") else None
        return t, json.dumps(d, ensure_ascii=False)[:300], None

    def show_entry(self) -> None:
        sel = self.timeline.selection()
        if not sel:
            return
        e = self.entries.get(sel[0])
        if e is None:
            return
        orig = self.d.s.journal.original(e)
        payload = orig.get("payload")
        if e["type"] == "model_request" and isinstance(payload, list):
            text = "\n\n".join(f"[{m['role']}]\n{m.get('content') or ''}" + (
                "\n调用：" + json.dumps(m["tool_calls"], ensure_ascii=False) if m.get("tool_calls") else "") for m in payload)
        elif e["type"] == "model_response" and isinstance(payload, dict):
            text = (payload.get("text") or "") + ("\n\n调用工具：\n" + json.dumps(payload.get("tool_calls"), ensure_ascii=False, indent=2)
                                                  if payload.get("tool_calls") else "")
        elif isinstance(payload, str):
            text = payload
        else:
            text = json.dumps(orig.get("data"), ensure_ascii=False, indent=2) if payload is None else json.dumps(payload, ensure_ascii=False, indent=2)
        self._set_text(self.detail, text[:200_000])


def enable_high_dpi() -> None:
    """Sharp text on high-DPI screens. Must run before the first Tk window is created."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="codedoctor gui")
    p.add_argument("--config", required=True)
    args = p.parse_args(argv)
    enable_high_dpi()
    root = tk.Tk()
    root.withdraw()
    try:
        cfg = config_mod.load(args.config)
        backend = Backend(cfg)
    except AlreadyRunning as e:
        messagebox.showerror("Lumen", f"{e}\n\n这个项目已经有一个 Lumen 在运行（可能是另一个窗口或命令行）。")
        return 1
    except Exception as e:
        messagebox.showerror("Lumen 启动失败", f"{type(e).__name__}: {e}")
        return 1
    root.deiconify()
    App(root, cfg, backend)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
