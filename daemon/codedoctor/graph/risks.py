"""Deterministic risk detectors over the coupling graph (schemas/graph/risk).

Each detector looks for a structural pattern that commonly produces cross-module
bugs. A finding is a lead for the logic head, never a bug report. Detectors focus
on persistent data (tables) and business state (gold, inventory, orders, ...):
in-memory UI bookkeeping writes many fields from many events and is normal.
"""

from __future__ import annotations

import hashlib
import re

from codedoctor.graph.model import Graph, node_type

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
BUSINESS_WORDS = {
    "gold", "coin", "coins", "money", "balance", "cash", "credit", "credits", "price", "cost", "pay", "payment", "order",
    "orders", "inventory", "item", "items", "stock", "reward", "rewards", "score", "scores", "exp", "xp", "level", "hp",
    "health", "ammo", "kill", "kills", "death", "deaths", "rank", "match", "session", "account", "wallet", "ledger",
    "purchase", "buy", "sell", "trade", "bag", "equip", "equipment", "skin", "skins", "friend", "friends", "stats",
    "points", "ticket", "tickets", "quota", "vip", "energy", "stamina", "diamond", "diamonds", "gem", "gems",
    "currency", "economy", "damage", "loot", "shop", "player", "players", "users", "user",
}
# Browser / runtime events: listening to them without an emitter in the project is normal.
PLATFORM_EVENTS = {
    "click", "dblclick", "mousedown", "mouseup", "mousemove", "mouseover", "mouseout", "mouseenter", "mouseleave", "wheel",
    "contextmenu", "keydown", "keyup", "keypress", "input", "change", "submit", "focus", "blur", "focusin", "focusout",
    "load", "unload", "beforeunload", "resize", "scroll", "error", "message", "open", "close", "pointerdown", "pointerup",
    "pointermove", "pointercancel", "pointerover", "pointerout", "pointerenter", "pointerleave", "pointerlockchange",
    "pointerlockerror", "touchstart", "touchend", "touchmove", "touchcancel", "visibilitychange", "fullscreenchange",
    "fullscreenerror", "gamepadconnected", "gamepaddisconnected", "ended", "play", "playing", "pause", "canplay",
    "canplaythrough", "loadeddata", "loadedmetadata", "timeupdate", "abort", "progress", "storage", "popstate",
    "hashchange", "online", "offline", "unhandledrejection", "rejectionhandled", "console", "pageerror", "request",
    "response", "requestfinished", "requestfailed", "connection", "data", "end", "drain", "finish", "readable",
    "listening", "exit", "uncaughtException", "SIGINT", "SIGTERM", "animationend", "animationstart", "transitionend",
    "webglcontextlost", "webglcontextrestored", "dragstart", "drag", "dragend", "dragover", "dragenter", "dragleave",
    "drop", "copy", "paste", "cut", "select", "selectionchange", "DOMContentLoaded", "readystatechange", "upgrade",
    "ping", "pong", "headers", "beforeinstallprompt", "devicemotion", "deviceorientation", "orientationchange",
    "compositionstart", "compositionend", "loadstart", "loadend", "timeout", "success", "complete", "statechange",
}


def _rid(pattern: str, *parts: str) -> str:
    return "rsk_" + hashlib.sha256("|".join((pattern, *parts)).encode()).hexdigest()[:16]


def _loc(g: Graph, entity: str, line: int | None = None) -> dict | None:
    n = g.nodes.get(entity)
    if n is None or not n.path:
        return None
    return {"path": n.path, "line": line or n.line or 1}


def _short(entity: str) -> str:
    return entity.split(":", 3)[-1]


def _words(name: str) -> list[str]:
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", name) if w]


def _is_business(entity: str) -> bool:
    return any(w in BUSINESS_WORDS for w in _words(_short(entity).split("/", 1)[-1]))


def _entries_reaching(g: Graph, entity: str, max_depth: int = 8) -> list[str]:
    """Entry points (routes, events, messages) whose handling can reach `entity` through calls only.
    State reads are deliberately not followed: reading a value does not make you its entry point."""
    seen, frontier, entries = {entity}, [entity], set()
    for _ in range(max_depth):
        nxt = []
        for cur in frontier:
            for e in g.inc.get(cur, []):
                if e.rel in ("calls", "handles", "consumes") and e.src not in seen:
                    seen.add(e.src)
                    if node_type(e.src) in ("route", "event", "ws_msg"):
                        entries.add(e.src)
                    else:
                        nxt.append(e.src)
        frontier = nxt
    return sorted(entries)


def _server_entries(entries: list[str]) -> list[str]:
    return [e for e in entries if node_type(e) in ("route", "ws_msg")]


def detect(g: Graph, code_version: str) -> list[dict]:
    found: list[tuple[int, dict]] = []

    def add(score, pattern, severity, entities, locations, explanation, fault_model, how):
        locs = [l for l in locations if l]
        if not locs:
            return
        found.append((score, {"cd_schema": "cd.graph.risk/0", "id": _rid(pattern, *entities), "pattern": pattern,
                              "severity": severity, "entities": entities, "locations": locs[:20],
                              "explanation": explanation[:4000], "fault_model": fault_model,
                              "how_to_verify": how[:2000], "code_version": code_version}))

    symbols = {k: n for k, n in g.nodes.items() if n.type == "symbol"}

    def store_writes(sid: str) -> set[str]:
        return {e.dst for e in g.out.get(sid, []) if e.rel == "writes"}

    # 1. persistent or business state written from several entry points
    for state, n in g.nodes.items():
        if n.type not in ("state", "table"):
            continue
        writers = sorted({e.src for e in g.inc.get(state, []) if e.rel == "writes"})
        if len(writers) < 2:
            continue
        is_table, business = n.type == "table", _is_business(state)
        if not (is_table or business):
            continue
        entries = sorted({en for w in writers for en in _entries_reaching(g, w)})
        server = _server_entries(entries)
        if len(entries) < 2:
            continue
        guarded = all(symbols.get(w) and symbols[w].attrs.get("has_tx") for w in writers)
        score = (3 if is_table else 2) + (2 if len(server) >= 2 else 1 if len(entries) >= 2 else 0) + (0 if guarded else 1)
        severity = "high" if score >= 5 else "medium" if score >= 4 else "low"
        add(score, "shared_state_multi_writer", severity, [state, *writers[:10]],
            [_loc(g, w, next((e.line for e in g.out.get(w, []) if e.rel == "writes" and e.dst == state), None)) for w in writers],
            f"{_short(state)} is written by {len(writers)} functions reachable from {len(entries)} entry points "
            f"({', '.join(_short(x) for x in (server or entries)[:6])}){'' if guarded else ', with no transaction or lock'}. "
            "Concurrent or repeated entry can leave it inconsistent.",
            "fm:concurrent_write",
            f"Trigger two of these entry points at the same time for the same record and compare {_short(state)} with its source of truth.")

    # 2. retry / reconnect / replay paths that reach persistent or server-side business writes without an idempotency key.
    #    A client retry that only refreshes client state cannot charge twice; one that crosses the network can.
    for sid, n in symbols.items():
        if not n.attrs.get("retryish"):
            continue
        lang = n.attrs.get("language")
        own_store = {"python": "py", "javascript": "js"}.get(lang, lang)
        starts = [sid] + [e.src for e in g.inc.get(sid, []) if e.rel == "calls"]
        reached = {}
        for st in starts:
            for ent, (d, path) in g.reach(st, "down", max_depth=6).items():
                if ent in reached:
                    continue
                t = node_type(ent)
                crossed = any(node_type(e.dst) in ("route", "ws_msg") for e in path)
                if t == "table" or (t == "state" and _is_business(ent) and (crossed or lang == "python"
                                                                            or not ent.split(":", 3)[3].startswith(own_store + "/"))):
                    reached[ent] = path
        if not reached:
            continue
        path_symbols = {e.src for p in reached.values() for e in p if node_type(e.src) == "symbol"}
        if any(symbols.get(s) and symbols[s].attrs.get("has_idem") for s in path_symbols):
            continue
        targets = sorted(reached)
        tables = [t for t in targets if node_type(t) == "table"]
        score = 6 if tables else 4
        add(score, "retry_path_to_write", "high" if tables or len(targets) >= 2 else "medium", [sid, *targets[:10]],
            [_loc(g, sid)] + [_loc(g, s) for s in sorted(path_symbols)][:10],
            f"{n.name} retries / replays work, and that path writes {', '.join(_short(t) for t in targets[:6])} "
            "with no idempotency key anywhere on the path. A lost response or a reconnect can apply the same change twice.",
            "fm:duplicate_request",
            "Make the first attempt succeed on the server but drop its response (or disconnect), let the retry/replay run, "
            "then check that the write happened exactly once.")

    # 3. one function writes several persistent / business stores without a transaction
    for sid, n in symbols.items():
        if n.attrs.get("has_tx"):
            continue
        stores = store_writes(sid)
        tables = [s for s in stores if node_type(s) == "table"]
        business = [s for s in stores if node_type(s) == "state" and _is_business(s)]
        if len(tables) >= 2:
            score, severity = 5, "high"
        elif tables and len(stores) >= 2:
            score, severity = 4, "medium"
        elif len(business) >= 2:
            score, severity = 2, "low"
        else:
            continue
        add(score, "multi_write_without_transaction", severity, [sid, *sorted(stores)[:10]],
            [_loc(g, sid, ln) for ln in n.attrs.get("write_lines", [])[:5]] or [_loc(g, sid)],
            f"{n.name} writes {len(stores)} stores ({', '.join(_short(s) for s in sorted(stores)[:6])}) "
            "without a transaction: a failure between the writes leaves them inconsistent.",
            "fm:partial_failure",
            "Inject a failure after the first write (e.g. make the second write raise) and check the stores still agree.")

    # 4. a business path returns nothing / false before its persistent or business writes
    for sid, n in symbols.items():
        early, wlines = n.attrs.get("early_returns", []), n.attrs.get("write_lines", [])
        hit = [ln for ln in early if any(w > ln for w in wlines)]
        if not hit:
            continue
        important = [s for s in store_writes(sid) if node_type(s) == "table" or _is_business(s)]
        if not important:
            continue
        server = _server_entries(_entries_reaching(g, sid))
        callers = sorted({e.src for e in g.inc.get(sid, []) if e.rel == "calls"})
        score = 3 + (1 if server else 0) + (1 if any(node_type(s) == "table" for s in important) else 0)
        add(score, "silent_noop_path", "medium" if server else "low", [sid, *callers[:10]],
            [_loc(g, sid, hit[0])] + [_loc(g, c) for c in callers[:5]],
            f"{n.name} returns an empty / false value at line {hit[0]} and skips its writes to "
            f"{', '.join(_short(s) for s in important[:4])} without raising. Callers ({len(callers)}) must notice this; "
            "if one treats it as success the user sees nothing happen.",
            "fm:silent_noop",
            f"Call {n.name} with input that takes the early return and check what each caller returns to the user.")

    # 5/6. project events with no listener / listeners with no event
    for ent, n in g.nodes.items():
        if n.type not in ("event", "ws_msg") or n.name in PLATFORM_EVENTS:
            continue
        emitters = [e for e in g.inc.get(ent, []) if e.rel == "emits"]
        consumers = [e for e in g.out.get(ent, []) if e.rel == "consumes"]
        business = _is_business(ent)
        if emitters and not consumers:
            add(2 if business else 1, "event_without_listener", "medium" if business and n.type == "ws_msg" else "low",
                [ent, *[e.src for e in emitters][:10]], [{"path": e.path, "line": e.line} for e in emitters if e.path],
                f"{n.name} is emitted but nothing in the scanned code listens for it (it may be handled by code outside the project).",
                "fm:lost_message", f"Emit {n.name} and check whether any visible effect follows.")
        if consumers and not emitters:
            add(2 if business else 1, "listener_without_event", "medium" if business else "low",
                [ent, *[e.dst for e in consumers][:10]], [{"path": e.path, "line": e.line} for e in consumers if e.path],
                f"Something listens for {n.name} but nothing in the scanned code emits it: the handler may never run "
                "(unless a server or library outside the project sends it).",
                "fm:dead_handler", f"Search for the producer of {n.name}; if none exists, the listener's work never happens.")

    # 7. client calls a route no scanned server code handles
    if any(n.type == "route" and n.attrs.get("server") for n in g.nodes.values()):
        for ent, n in g.nodes.items():
            if n.type != "route" or n.attrs.get("server"):
                continue
            callers = [e for e in g.inc.get(ent, []) if e.rel == "calls"]
            if callers:
                add(4, "client_route_without_handler", "medium", [ent, *[e.src for e in callers][:10]],
                    [{"path": e.path, "line": e.line} for e in callers if e.path],
                    f"Client code calls {_short(ent)} but no scanned server route handles it "
                    "(it may live in a server outside the scanned project).",
                    "fm:contract_mismatch", "Send the request and check the server's response status.")

    found.sort(key=lambda x: (SEVERITY_ORDER[x[1]["severity"]], -x[0], x[1]["pattern"], x[1]["id"]))
    return [r for _, r in found]
