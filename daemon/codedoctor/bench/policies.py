"""Scripted agent behaviour for the reasoning bench: the deterministic baseline.

Each policy is what a model of a certain quality would do on a scenario: `careful_*` reasons
well, the others make one typical reasoning mistake (jumping to a plausible wrong lead,
leaving competing hypotheses open and missing the link to the symptom). With scripted agents
the bench measures the SYSTEM: whether its rules and checks notice those mistakes, and that
they stay quiet when the reasoning is sound. With a model the user picks, the same scenarios
measure the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

S = "ent:symbol:shop:"
_EV = re.compile(r"evidence: (ev:code:\S+)")
_CLM = re.compile(r"claim accepted as (clm_[0-9A-Z]{26})")


@dataclass
class Policy:
    mode: str                       # basic | cluster
    scripts: dict[str, list]        # agent id -> scripted turns


def last_evidence(msgs) -> str:
    for m in reversed(msgs):
        found = _EV.findall(m.content or "")
        if found:
            return found[0]
    raise RuntimeError("no evidence in conversation")


def accepted(msgs) -> list[str]:
    return [c for m in msgs if m.role == "tool" for c in _CLM.findall(m.content or "")]


def _claim(msgs, text: str, subject: str, relation: str, obj: str, contains: str, test: str, **extra) -> dict:
    ev = last_evidence(msgs)
    return {"tool_calls": [{"name": "submit_claim", "arguments": {"claim": {
        "claim_type": "hypothesis", "evidence_level": "inferred",
        "statement": {"text": text, "subject": subject, "relation": relation, "object": obj},
        "scope": {"code_version": ev.split(":")[2]},
        "evidence": [{"id": ev, "role": "supports", "shows": text[:200], "assert": [{"op": "text_contains", "text": contains}]}],
        "falsification": {"method": "test", "intervention": True, "description": test}, **extra}}}]}


def _read(path: str, start: int | None = None, end: int | None = None) -> dict:
    args: dict = {"path": path}
    if start:
        args.update(start_line=start, end_line=end)
    return {"tool_calls": [{"name": "read_file", "arguments": args}]}


def _reconnect_careful_cluster() -> Policy:
    return Policy("cluster", {
        "head-dispatch": [
            {"tool_calls": [{"name": "consult", "arguments": {"question": "哪些模块可能让比赛奖励到账两次？"}}]},
            {"tool_calls": [{"name": "delegate", "arguments": {
                "agent": "worker-1", "title": "核实重连重放结算",
                "instructions": "读 server/session.py 和 server/rewards.py，确认 reconnect 是否会让 settle 执行两次。",
                # every project may change code (the user removed read-only members): the head names the worker's files
                "files": ["server/session.py", "server/rewards.py"]}}]},
            {"tool_calls": [{"name": "wait_for", "arguments": {}}]},
            # the detail checklist is still open, so the head is sent back twice (ADR 0014) and keeps its answer
            *[{"text": "已验证：reconnect 会重放挂起的 settle 请求，settle 调用的 add_gold 没有幂等键，奖励和 ledger 都会多记一次"
                       "（主张由 guardian 独立复查后提交）。未覆盖：并发场景。"}] * 3,
        ],
        "head-logic": [
            {"tool_calls": [{"name": "graph_common_cause", "arguments": {"symptoms": ["/api/session/reconnect", "/api/match/settle"]}}]},
            {"tool_calls": [{"name": "graph_risks", "arguments": {"pattern": "retry_path_to_write"}}]},
            {"text": "共同路径：reconnect -> settle -> add_gold 写 py/gold 和 ledger，没有幂等键。建议让 worker 核实 session.py。"},
        ],
        # the worker is the hands: it reads and answers, it files no claims; its guardian re-reads the code and states
        # what was found
        "worker-1": [
            _read("server/session.py", 5, 12),
            {"text": "reconnect() 对挂起的结算请求再次调用 settle()；add_gold 没有幂等键。"},
        ],
        "guardian-1": [
            _read("server/session.py", 5, 12),
            lambda msgs: _claim(msgs, "reconnect 会重放挂起的 /api/match/settle 请求，比赛奖励因此会发两次",
                                S + "server/session.py#reconnect", "causes", "ent:state:shop:py/gold", "settle(pending, player)",
                                "结算后丢弃响应再重连，比较金币与 ledger"),
            {"text": "自己重读了 session.py：循环会对每个挂起的结算请求调用 settle()，已提交主张。另外注意：spend_gold 写 players 和 "
                     "ledger 没有事务。"},
        ],
    })


def _reconnect_jumps() -> Policy:
    return Policy("basic", {"doctor": [
        _read("web/match.js"),
        lambda msgs: _claim(msgs, "finishMatch 把 /api/match/settle 请求发了两次，奖励因此重复到账",
                            S + "web/match.js#finishMatch", "causes", "ent:state:shop:py/gold", "/api/match/settle",
                            "抓包统计 finishMatch 一次调用发出的 settle 请求数"),
        {"text": "根因：web/match.js 的 finishMatch 把结算请求发了两次，奖励因此重复到账。修复：finishMatch 只发一次。"},
    ]})


def _buy_careful() -> Policy:
    return Policy("basic", {"doctor": [
        _read("server/wallet.py", 10, 16),
        lambda msgs: _claim(msgs, "spend_gold 在金币不足时返回 None，buy 据此直接返回 200 {}",
                            S + "server/wallet.py#spend_gold", "causes", S + "server/shop.py#buy", "return None",
                            "金币不足时调用 buy，检查返回值"),
        _read("server/shop.py"),
        lambda msgs: _claim(msgs, "buy 返回 200 {} 不带 item，onBuyClick 只在 data.item 存在时更新界面，所以看起来没反应",
                            S + "server/shop.py#buy", "causes", S + "web/shop.js#ShopUI.onBuyClick",
                            'return {"status": 200, "body": {}}', "金币不足时点购买，检查响应与界面",
                            depends_on=accepted(msgs)[:1]),
        _read("web/hud.js"),
        lambda msgs: _claim(msgs, "gold_changed 没有人 emit，HUD 不刷新，所以购买看起来没反应",
                            "ent:event:shop:gold_changed", "causes", S + "web/shop.js#ShopUI.onBuyClick", "gold_changed",
                            "购买成功后观察 HUD 是否更新"),
        lambda msgs: {"tool_calls": [{"name": "withdraw_claim", "arguments": {
            "claim_id": accepted(msgs)[-1],
            "reason": "排除：购买成功时 hud 通过 purchase_success 更新；gold_changed 与本症状无关（它是另一个缺陷）"}}]},
        {"text": "结论（推断，尚未经独立复查）：金币不足时 spend_gold 返回 None，buy 返回 200 {}，onBuyClick 只在有 item 时更新界面，"
                 "所以玩家看到没反应。已排除 gold_changed 的解释。建议：返回明确错误码并在界面提示。"},
    ]})


def _buy_competing_open() -> Policy:
    return Policy("basic", {"doctor": [
        _read("server/wallet.py", 10, 16),
        lambda msgs: _claim(msgs, "spend_gold 在金币不足时返回 None，购买接口返回 200 {}",
                            S + "server/wallet.py#spend_gold", "causes", "ent:route:shop:POST:/api/shop/buy", "return None",
                            "金币不足时调用购买接口，检查响应"),
        _read("web/hud.js"),
        lambda msgs: _claim(msgs, "gold_changed 没有人 emit，HUD 不刷新，所以购买看起来没反应",
                            "ent:event:shop:gold_changed", "causes", S + "web/shop.js#ShopUI.onBuyClick", "gold_changed",
                            "购买成功后观察 HUD 是否更新"),
        {"text": "原因是 spend_gold 在金币不足时返回 None，购买接口因此返回 200 {}。"},
    ]})


POLICIES = {
    ("reconnect-double-reward", "careful_cluster"): _reconnect_careful_cluster,
    ("reconnect-double-reward", "jumps_to_conclusion"): _reconnect_jumps,
    ("buy-does-nothing", "careful_basic"): _buy_careful,
    ("buy-does-nothing", "competing_open"): _buy_competing_open,
}
