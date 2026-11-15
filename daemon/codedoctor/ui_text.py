"""Chinese display text shared by the desktop windows."""

from __future__ import annotations

import json
from datetime import datetime

STATE_CN = {"queued": "排队中", "running": "运行中", "finished": "已结束"}
OUTCOME_CN = {"done": "完成", "failed": "失败", "blocked": "被拦下", "budget_exhausted": "预算用完",
              "stalled": "无进展已停止", "cancelled": "已取消", "interrupted": "中断"}
AGENT_CN = {"idle": "空闲", "working": "工作中", "paused": "已暂停", "stopped": "已停止"}
ROLE_CN = {"general": "单 Agent", "head_dispatch": "调度首脑", "head_logic": "逻辑首脑", "worker": "执行者",
           "guardian": "监督者", "investigator": "调查员", "compressor": "压缩"}
TOOL_CN = {"list_dir": "查看目录", "read_file": "读取文件", "search_text": "搜索文本", "run_command": "执行命令",
           "read_evidence": "读取证据", "remember": "写入记忆", "recall": "检索记忆", "submit_claim": "提交结论",
           "check_claim": "检查结论", "withdraw_claim": "撤回结论", "review_claim": "审查结论", "send_message": "发送消息",
           "graph_overview": "耦合图谱概况", "graph_rebuild": "重建耦合图谱", "graph_find": "图谱查找",
           "graph_neighbors": "直接关系", "graph_impact": "影响范围", "graph_common_cause": "共同根因",
           "graph_risks": "风险线索", "delegate": "分派任务", "wait_for": "等待结果", "consult": "咨询逻辑首脑",
           "scout": "派侦察兵", "tell_fixers": "转告修复组",
           "task_status": "子任务状态", "raise_objection": "提出异议", "withdraw_objection": "撤回异议",
           "read_note": "读取记忆全文", "cluster_inventory": "列出可做的业务实验", "cluster_candidates": "找业务共同上游",
           "cluster_open": "冻结调查计划", "cluster_dispatch": "分派业务实验", "cluster_run": "执行业务实验",
           "cluster_status": "调查进度", "cluster_impact": "业务影响树", "report_anomaly": "上报异常",
           "anomaly_inbox": "查看异常收件箱", "decide_anomaly": "首脑决策异常", "resolve_anomaly": "确认异常已解决",
           "checklist_update": "细节审查清单", "edit_file": "修改代码", "create_file": "新建文件",
           "claude_code": "Claude Code", "codex": "Codex", "ask_team": "交给团队", "spawn_helpers": "派一次性助手",
           "web_search": "搜索网页", "fetch_page": "打开网页", "wait_and_look": "等待并查看画面",
           "browser_open": "浏览器打开", "browser_read": "浏览器读页面", "browser_back": "浏览器后退",
           "browser_click": "浏览器点击", "browser_type": "浏览器输入", "browser_look": "看网页画面", "browser_mouse": "在网页里用鼠标",
           "browser_keys": "在网页里按键", "browser_console": "看网页报错", "screenshot": "看屏幕", "list_windows": "列出窗口",
           "mouse_move": "移动鼠标", "mouse_click": "点击鼠标", "type_text": "键盘输入", "press_keys": "按键",
           "look_around": "转动视角", "aim_at": "对准目标", "hold_keys": "按住按键", "hold_mouse": "按住鼠标",
           "launch_app": "启动程序", "close_app": "关闭程序", "video_project": "查看视频", "video_edit": "剪辑视频",
           "video_render": "导出视频", "code3d_project": "查看 3D 项目", "code3d_run": "运行 3D 场景", "maker_read": "查看作品", "maker_run": "制作"}
CLAIM_CN = {"proposed": "待验证", "supported": "成立", "refuted": "被推翻", "needs_revalidation": "需要重新验证",
            "superseded": "已被取代", "withdrawn": "已撤回"}
LEVEL_CN = {"observed": "观测到", "reproduced": "已复现", "inferred": "推断", "speculated": "猜测"}
VERDICT_CN = {"reverified": "已核实", "counterexample": "反例", "insufficient_evidence": "证据不足"}
RISK_CN = {"shared_state_multi_writer": "多个入口写同一数据", "retry_path_to_write": "重试/重连会重复写入",
           "multi_write_without_transaction": "多处写入没有事务", "silent_noop_path": "静默失败（不报错直接返回）",
           "event_without_listener": "事件发出但无人监听", "listener_without_event": "监听的事件无人发出",
           "client_route_without_handler": "调用了后端不存在的接口"}
SEVERITY_CN = {"high": "高", "medium": "中", "low": "低"}
ESCALATION_CN = {"model_unavailable": "模型不可用", "account": "服务账户（余额或密钥）", "permission_needed": "需要授权", "contradiction": "结论冲突",
                 "budget": "预算", "stalled": "无进展", "anomaly": "异常", "interrupted": "任务中断",
                 "head_disagreement": "首脑意见分歧", "safety_veto": "安全否决", "other": "其他"}
RESUMABLE = {"interrupted", "blocked", "budget_exhausted", "stalled"}

# Business investigations (ADR 0010, docs/adr/0011)
HYPOTHESIS_CN = {"refuted_in_declared_scope": "已排除（在声明的实验范围内）", "compatible_not_proven": "与观察相符（不等于已证明）",
                 "untested": "尚未检验"}
PURPOSE_CN = {"discriminate": "区分假设", "regression": "影响范围回归"}
SIGNATURE_CN = {"holds": "业务规则成立", "violated": "业务规则被破坏"}
CHECK_CN = {"independently_reproduced_in_scope": "执行者与监督者独立复现一致", "planned": "尚未开始",
            "awaiting_independent_execution": "等待执行者和监督者都独立跑完", "running_or_interrupted": "运行中或被中断",
            "disputed": "执行者和监督者的结果不一致", "not_independent": "两次运行不独立",
            "incomplete_evidence": "实验记录不完整", "invalid_evidence": "实验记录校验失败",
            "invalid_or_unavailable_evidence": "证据缺失或无法校验", "wrong_harness": "执行器与冻结的计划不符",
            "wrong_actor": "执行的 Agent 与分配不符", "wrong_collector": "证据来源不对",
            "invalid_harness_evidence": "执行器源码证据校验失败", "oracle_disagreement": "重新计算的业务规则与记录不一致",
            "bad_control": "对照组（基线或恢复）没有通过", "unstable_signature": "故障结果前后不稳定"}
_BLOCKING_CN = {"competing hypotheses remain": "仍有多个假设与观察相符，还没区分出来",
                "observations contradict all hypotheses": "观察结果与所有假设都矛盾",
                "agent task not successfully settled": "Agent 任务还没有成功结束",
                "unresolved head objection": "首脑的异议还没有解决",
                "affected business regression failed": "受影响业务的回归检查失败"}


def blocking_cn(reason: str) -> str:
    """'<id>: <code>' or a sentence from the investigation service, in Chinese where it is a known one."""
    head, sep, tail = reason.partition(": ")
    if reason in _BLOCKING_CN:
        return _BLOCKING_CN[reason]
    if sep and (tail in CHECK_CN or tail in _BLOCKING_CN):
        return f"{head}：{CHECK_CN.get(tail) or _BLOCKING_CN[tail]}"
    return reason


def local_time(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")


def parse_ts(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def task_status(row: dict) -> str:
    if row["state"] == "finished":
        return OUTCOME_CN.get(row["outcome"], row["outcome"] or "已结束")
    return STATE_CN.get(row["state"], row["state"])


def duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} 秒"
    if seconds < 3600:
        return f"{seconds // 60} 分 {seconds % 60} 秒"
    return f"{seconds // 3600} 小时 {seconds % 3600 // 60} 分"


def short_entity(entity: str) -> str:
    return entity.split(":", 3)[-1] if entity.startswith("ent:") else entity


def describe_tool_call(tool: str, args: dict) -> str:
    """One-line, human description of a tool call."""
    a = args or {}
    if tool == "read_file":
        rng = ""
        if a.get("start_line"):
            rng = f"  第 {a['start_line']}–{a.get('end_line', '…')} 行"
        return f"读取 {a.get('path', '')}{rng}"
    if tool == "list_dir":
        return f"查看目录 {a.get('path', '.')}"
    if tool == "search_text":
        return f"搜索 “{a.get('query', '')}”" + (f"  于 {a['path']}" if a.get("path") else "")
    if tool == "run_command":
        cmd = a.get("command", "")
        return f"执行命令  {cmd.splitlines()[0][:90] if cmd else ''}" + (" …" if "\n" in cmd else "")
    if tool == "edit_file":
        old, new = a.get("old", ""), a.get("new", "")
        return f"修改 {a.get('path', '')}  （-{len(old.splitlines()) or 1} +{len(new.splitlines()) or 1} 行）"
    if tool == "create_file":
        return f"新建 {a.get('path', '')}  （{len(a.get('content', '').splitlines())} 行）"
    if tool == "recall":
        return f"检索长期记忆 “{a.get('query', '')}”"
    if tool == "remember":
        return f"写入长期记忆：{a.get('text', '')[:70]}"
    if tool == "submit_claim":
        st = (a.get("claim") or {}).get("statement") or {}
        return f"提交结论：{st.get('text', '')[:80]}"
    if tool == "review_claim":
        return f"独立复查 {a.get('claim_id', '')} → {VERDICT_CN.get(a.get('verdict'), a.get('verdict', ''))}"
    if tool in ("check_claim", "withdraw_claim"):
        return f"{TOOL_CN[tool]} {a.get('claim_id', '')}"
    if tool == "graph_overview":
        return "查看耦合图谱概况"
    if tool == "graph_find":
        return f"在耦合图谱中查找 “{a.get('query', '')}”"
    if tool in ("graph_neighbors", "graph_impact"):
        return f"{TOOL_CN[tool]}：{short_entity(a.get('entity', ''))}"
    if tool == "graph_common_cause":
        return "寻找共同根因：" + "、".join(short_entity(s) for s in a.get("symptoms", []))
    if tool == "graph_risks":
        return "查看风险线索" + (f"（{a['pattern']}）" if a.get("pattern") else "")
    if tool == "delegate":
        return f"派给 {a.get('agent', '')}：{a.get('title', '')}"
    if tool == "ask_team":  # the Lumen team (agents/team.py)
        from codedoctor.agents import team

        jobs = [j for j in a.get("jobs") or [] if isinstance(j, dict)]
        names = "、".join(team.BY_ID[j["member"]].name if j.get("member") in team.BY_ID else str(j.get("member"))
                         for j in jobs)
        first = str(jobs[0].get("task", "")).splitlines()[0][:60] if jobs else ""
        return f"交给 {names}：{first}" + ("……" if len(jobs) > 1 else "")
    if tool == "spawn_helpers":
        jobs = [str(j) for j in a.get("jobs") or []]
        return f"派 {len(jobs)} 个一次性助手：{jobs[0].splitlines()[0][:60] if jobs else ''}"
    if tool == "web_search":
        return f"搜索网页 “{str(a.get('query', ''))[:80]}”"
    if tool == "fetch_page":
        return f"打开网页 {str(a.get('url', ''))[:100]}"
    if tool == "browser_open":
        return f"浏览器打开 {str(a.get('url', ''))[:100]}"
    if tool == "browser_click":
        return f"浏览器点击第 {a.get('ref', '')} 项"
    if tool == "browser_type":
        return f"浏览器输入第 {a.get('ref', '')} 项：{str(a.get('text', ''))[:60]}"
    if tool == "wait_and_look":
        return f"等 {a.get('seconds', '')} 秒再看画面"
    if tool == "scout":
        titles = [sc.get("title", "") for sc in a.get("scenarios") or [] if isinstance(sc, dict)]
        return f"派侦察兵查 {len(titles)} 个场景：" + "、".join(titles[:6]) + ("……" if len(titles) > 6 else "")
    if tool == "tell_fixers":
        return "转告修复组：" + str(a.get("text", ""))[:120]
    if tool == "wait_for":
        return "等待子任务完成（等待期间不消耗 token）"
    if tool == "consult":
        return f"咨询逻辑首脑：{a.get('question', '')[:70]}"
    if tool == "raise_objection":
        return f"提出异议：{a.get('text', '')[:70]}"
    if tool == "send_message":
        return f"发消息给 {a.get('to', '')}：{a.get('text', '')[:60]}"
    if tool == "report_anomaly":
        return f"上报异常（{'假设' if a.get('hypothesis') else '已观察到'}）：{a.get('title', '')[:70]}"
    if tool == "decide_anomaly":
        from codedoctor.agents.anomalies import DECISIONS

        return f"决策异常 {a.get('anomaly_id', '')} → {DECISIONS.get(a.get('decision'), a.get('decision', ''))}"
    if tool == "resolve_anomaly":
        return f"确认异常已解决 {a.get('anomaly_id', '')}"
    if tool == "anomaly_inbox":
        return "查看异常收件箱" + (f" {a['anomaly_id']}" if a.get("anomaly_id") else "")
    if tool in ("claude_code", "codex"):  # the user's Claude Code / Codex at work (codedoctor/engines.py)
        what = {"Read": "读取", "Edit": "修改", "MultiEdit": "修改", "Write": "写入", "Delete": "删除", "Bash": "执行命令",
                "Grep": "搜索", "Glob": "查找文件", "LS": "查看目录", "TodoWrite": "更新待办", "Task": "派子代理",
                "WebSearch": "搜索网页", "video_project": "查看视频", "video_edit": "剪辑视频",
                "video_render": "导出视频", "code3d_project": "查看 3D 项目", "code3d_run": "运行 3D 场景", "maker_read": "查看作品", "maker_run": "制作"}.get(a.get("tool")) or TOOL_CN.get(a.get("tool"), a.get("tool", ""))
        detail = a.get("path") or a.get("command") or a.get("pattern") or a.get("description") or ""
        if a.get("tool") in ("Edit", "MultiEdit") and "minus" in a:
            detail += f"  （-{a['minus']} +{a['plus']} 行）"
        if tool == "codex":
            return f"Codex · {what} {str(detail)[:100]}".rstrip()
        return f"Claude Code · {what} {str(detail)[:100]}".rstrip()
    if tool == "checklist_update":
        if a.get("add"):
            return f"细节审查清单：新增“{a['add'][:50]}”"
        return f"细节审查清单：更新 {a['item']}" if a.get("item") else "查看细节审查清单"
    return f"{TOOL_CN.get(tool, tool)}  {json.dumps(a, ensure_ascii=False)[:80]}"


TOOL_ICON = {"edit_file": "✏", "create_file": "🆕", "read_file": "📄", "list_dir": "📁", "search_text": "🔍", "run_command": "⌨", "read_evidence": "🧾",
             "remember": "🧠", "recall": "🧠", "submit_claim": "✍", "check_claim": "☑", "withdraw_claim": "↩",
             "review_claim": "🛡", "send_message": "✉", "graph_overview": "🕸", "graph_rebuild": "🕸",
             "graph_find": "🕸", "graph_neighbors": "🕸", "graph_impact": "🕸", "graph_common_cause": "🎯",
             "graph_risks": "⚠", "delegate": "📨", "scout": "🔭", "tell_fixers": "📣", "wait_for": "⏳", "consult": "💬", "task_status": "📋",
             "raise_objection": "✋", "withdraw_objection": "✋", "read_note": "🧠", "cluster_inventory": "🧪",
             "cluster_candidates": "🎯", "cluster_open": "📌", "cluster_dispatch": "📨", "cluster_run": "🧪",
             "cluster_status": "📋", "cluster_impact": "🕸", "report_anomaly": "❗", "anomaly_inbox": "📥",
             "decide_anomaly": "⚖", "resolve_anomaly": "✅", "checklist_update": "☑"}
