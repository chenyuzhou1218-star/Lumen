"""Ray's hands on the built-in browser (desktop/browser.py): it opens pages, reads them, clicks and types, in a tab of
its own that the user can watch. The window owns the browser, so these work while the window is open.

Hard rules, here and not left to a model: nothing on this computer or the local network; no typing into password,
card or code fields; no click on what signs in, pays, sends, publishes or deletes - those stop and go to the user.
"""

from __future__ import annotations

import asyncio
import re

from codedoctor.agents.tools import TOOLS, Tool, ToolContext, ToolResult, _err, _obj

WAIT_S = 45
MAX_ELEMENTS_SHOWN = 150
SECRET_FIELD = re.compile(r"pass(word|wd|code)?|pwd|密码|口令|验证码|otp|one.?time|card|cvv|cvc|信用卡|银行卡|身份证|ssn|"
                          r"cc-|security.?code|安全码|token|api.?key", re.I)
USERS_CLICK = re.compile(r"登录|登入|注册|sign.?in|sign.?up|log.?in|支付|付款|购买|下单|结算|充值|转账|提交订单|确认订单|"
                         r"\b(pay|buy|purchase|checkout|order now|subscribe)\b|删除|注销|\b(delete|remove account)\b|"
                         r"发布|发送|\b(publish|send|post|submit)\b|同意|接受|\b(accept|agree)\b", re.I)


def _bridge(ctx: ToolContext):
    return getattr(ctx.services, "browser", None)


async def _call(ctx: ToolContext, op: str, *args):
    return await asyncio.wait_for(asyncio.wrap_future(ctx.services.browser.call(op, *args)), WAIT_S)


def _allowed(ctx: ToolContext) -> str | None:
    from codedoctor.agents.team import _web_allowed

    if _bridge(ctx) is None:
        return "the browser lives in the Lumen window; use web_search and fetch_page, or open the window"
    return _web_allowed(ctx)


def _page(result: dict | None) -> ToolResult:
    if not result or result.get("error"):
        return _err((result or {}).get("error", "the page did not answer"))
    lines = [f"{result.get('title', '')}", f"{result.get('url', '')}", "", result.get("text", ""), "", "Elements (use their number):"]
    for e in (result.get("elements") or [])[:MAX_ELEMENTS_SHOWN]:
        kind = e["tag"] + (f":{e['type']}" if e.get("type") and e["tag"] == "input" else "")
        lines.append(f"[{e['ref']}] {kind} {e.get('label', '')!r}" + (f" -> {e['href'][:120]}" if e.get("href") else ""))
    return ToolResult(ok=True, external=True, content="\n".join(lines))


def _user_named(ctx: ToolContext, url: str) -> str | None:
    """The address on this computer the user wrote in this task, if url is on it: their own game or site under test.
    A page or a model can name such an address too; only the user's words open it."""
    from urllib.parse import urlparse

    from codedoctor.agents import orchestration as orch

    netloc = urlparse(url).netloc
    root = orch.task_row(ctx.services, orch.root_of(ctx.services, ctx.task_id)) or {}
    words = str(orch.body_of(root).get("instructions", ""))
    return netloc if netloc and netloc in words else None


async def browser_open(ctx: ToolContext, args: dict) -> ToolResult:
    from codedoctor.agents.team import _public

    why = _allowed(ctx)
    if why:
        return _err(why)
    local = await asyncio.to_thread(_public, args["url"])
    if local:
        netloc = _user_named(ctx, args["url"])
        if netloc is None:
            return _err(local + " (an address on this computer opens only when the user wrote it in the task)")
        await _call(ctx, "allow", netloc)
    return _page(await _call(ctx, "open", args["url"]))


def _picture(ctx: ToolContext, result: dict | None, text: str) -> ToolResult:
    """What the page shows now, as a picture of its own pixels; kept only while the task runs, like screenshots."""
    from codedoctor.agents import orchestration as orch

    if not result or result.get("error"):
        return _err((result or {}).get("error", "the page did not answer"))
    ev = ctx.services.evidence.add_blob(result["png"], "image/png", source="tool", collected_by="browser.look/0",
                                        agent_id=ctx.agent_id, data_class=ctx.data_class)
    root = orch.root_of(ctx.services, ctx.task_id)
    ctx.services.__dict__.setdefault("_web_shots", {}).setdefault(root, []).append(ev)
    return ToolResult(ok=True, external=True, evidence=[ev], images=[ev],
                      content=f"{text}{result.get('title', '')} - {result.get('url', '')}\npicture: {result['width']}x{result['height']} px; "
                              "browser_mouse coordinates are pixels of this picture.")


async def browser_look(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    return _picture(ctx, await _call(ctx, "look"), "")


async def browser_mouse(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    action, x, y = args["action"], args["x"], args["y"]
    if action in ("click", "double"):
        info = await _call(ctx, "point", x, y)
        if info and USERS_CLICK.search(str(info.get("label", ""))):
            return _err(f"what is at ({x}, {y}) is {info.get('label')!r}: it signs in, pays, sends, publishes, deletes or agrees to "
                        "something. That is the user's to do. Stop and tell the user what is needed.")
    done = await _call(ctx, "mouse", action, float(x), float(y), float(args.get("to_x", x)), float(args.get("to_y", y)),
                       min(float(args.get("seconds", 0.5)), 5.0), int(args.get("delta", -240)))
    if done and done.get("error"):
        return _err(done["error"])
    return _picture(ctx, await _call(ctx, "look"), f"mouse {action} at ({x}, {y}) done. ")


async def browser_keys(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    if args.get("text"):
        info = await _call(ctx, "active")
        if info and (info.get("type") == "password" or SECRET_FIELD.search(_words(info))):
            return _err("the field in focus asks for a password, a card number, a code or the like: never typed by an agent. Stop "
                        "and tell the user.")
    done = await _call(ctx, "keys", args.get("keys") or [], str(args.get("text", "")), min(float(args.get("seconds", 0.1)), 5.0))
    if done and done.get("error"):
        return _err(done["error"])
    return _picture(ctx, await _call(ctx, "look"), "keys done. ")


async def browser_console(ctx: ToolContext, args: dict) -> ToolResult:
    if _bridge(ctx) is None:
        return _err("the browser lives in the Lumen window")
    rows = await _call(ctx, "console")
    if not rows:
        return ToolResult(ok=True, content="the page's console is empty: no errors or messages so far")
    lines = [f"[{level}] {msg[:400]} ({str(source)[-60:]}:{line})" for level, msg, line, source in rows[-60:]]
    return ToolResult(ok=True, external=True, content="\n".join(lines))


async def browser_read(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    return _page(await _call(ctx, "read"))


async def browser_back(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    return _page(await _call(ctx, "back"))


def _words(info: dict) -> str:
    return " ".join(str(info.get(k, "")) for k in ("type", "name", "id", "autocomplete", "placeholder", "label"))


async def browser_click(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    info = await _call(ctx, "describe", args["ref"])
    if info is None:
        return _err(f"no element [{args['ref']}] on this page; read the page again")
    words = " ".join(str(info.get(k, "")) for k in ("name", "id", "label"))  # not its type: every plain <button> is a "submit"
    if USERS_CLICK.search(words):
        return _err(f"[{args['ref']}] {info.get('label')!r} signs in, pays, sends, publishes, deletes or agrees to something: "
                    "that is the user's to do. Stop and tell the user what is needed.")
    return _page(await _call(ctx, "click", args["ref"]))


async def browser_type(ctx: ToolContext, args: dict) -> ToolResult:
    why = _allowed(ctx)
    if why:
        return _err(why)
    info = await _call(ctx, "describe", args["ref"])
    if info is None:
        return _err(f"no element [{args['ref']}] on this page; read the page again")
    if info.get("type") == "password" or SECRET_FIELD.search(_words(info)):
        return _err(f"[{args['ref']}] asks for a password, a card number, a code or the like: never typed by an agent. Stop "
                    "and tell the user.")
    return _page(await _call(ctx, "type", args["ref"], args["text"], bool(args.get("submit"))))


COORD = {"type": "number", "minimum": 0, "maximum": 8000}
REF = {"type": "integer", "minimum": 1, "maximum": 1000, "description": "the element's number from the latest page"}
BROWSER_TOOLS = [
    Tool("browser_open", "Open a web page in the Lumen browser, in your own tab the user can watch. Returns its text and "
                         "its numbered links, buttons and fields.",
         _obj({"url": {"type": "string", "minLength": 8, "maxLength": 2000}}, ["url"]), browser_open,
         effect_class="external", retry_safe=True),
    Tool("browser_read", "Read the page open in your browser tab again: its text and numbered elements.",
         _obj({}, []), browser_read),
    Tool("browser_back", "Go back one page in your browser tab.", _obj({}, []), browser_back, effect_class="external",
         retry_safe=False),
    Tool("browser_click", "Click a numbered element of the latest page. Anything that signs in, pays, sends, publishes, "
                          "deletes or agrees is refused: tell the user instead.",
         _obj({"ref": REF}, ["ref"]), browser_click, effect_class="external", retry_safe=False),
    Tool("browser_type", "Type into a numbered field of the latest page; submit=true sends the search or form with Enter. "
                         "Password, card and code fields are refused: tell the user instead.",
         _obj({"ref": REF, "text": {"type": "string", "minLength": 1, "maxLength": 4000}, "submit": {"type": "boolean"}},
              ["ref", "text"]), browser_type, effect_class="external", retry_safe=False),
]
BROWSER_TOOLS += [
    Tool("browser_look", "See the page in your browser tab as a picture: the way to work with a canvas, a 3D scene or a game, "
                         "where there are no elements to number. Your tab comes on screen in the Lumen window.",
         _obj({}, []), browser_look),
    Tool("browser_mouse", "Use a real mouse inside the page, at pixels of your latest browser_look picture; the user sees a little "
                          "cursor. action: click, double, right, move, hold (left button down for seconds), drag (to to_x, to_y over "
                          "seconds), wheel (delta: negative scrolls down). Returns a new picture. Use it to try a game or web app as a "
                          "person would and find what is broken.",
         _obj({"action": {"enum": ["click", "double", "right", "move", "hold", "drag", "wheel"]}, "x": COORD, "y": COORD, "to_x": COORD,
               "to_y": COORD, "seconds": {"type": "number", "minimum": 0, "maximum": 5}, "delta": {"type": "integer", "minimum": -2400, "maximum": 2400}},
              ["action", "x", "y"]), browser_mouse, effect_class="external", retry_safe=False),
    Tool("browser_keys", "Use real keys inside the page: keys are held together for seconds (['w'] 1.5 s to walk in a game, ['space'] to "
                         "jump, ['enter']); text types into what has the focus. Click first so the page has the keyboard. Returns a new picture.",
         _obj({"keys": {"type": "array", "maxItems": 4, "items": {"type": "string", "minLength": 1, "maxLength": 12}},
               "text": {"type": "string", "maxLength": 2000}, "seconds": {"type": "number", "minimum": 0, "maximum": 5}}, []),
         browser_keys, effect_class="external", retry_safe=False),
    Tool("browser_console", "The page's console: its errors, warnings and logs, the first place to look when something is wrong.",
         _obj({}, []), browser_console),
]
for _t in BROWSER_TOOLS:
    TOOLS[_t.name] = _t
