"""Message bus: the only channel between agents, the user and the system.

Messages (schemas/agent/message) are validated, stored permanently and
delivered in order. An agent with an empty inbox waits on an event and makes no
model calls.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from codedoctor import ids
from codedoctor.protocol.registry import validator
from codedoctor.store.db import Database, dumps

SCHEMA = "agent/message.schema.json"


class MessageError(ValueError):
    pass


class MessageBus:
    def __init__(self, db: Database):
        self.db = db
        self._events: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        self._owner_loop = None

    def bind_loop(self, loop):
        self._owner_loop = loop

    def notify(self, recipient):
        event = self._events[recipient]
        if self._owner_loop is not None and self._owner_loop.is_running():
            self._owner_loop.call_soon_threadsafe(event.set)
        else:
            event.set()

    def prepare(
        self,
        *,
        sender: str,
        recipient: str,
        kind: str,
        body: dict,
        thread_id: str | None = None,
        reply_to: str | None = None,
        data_class: str | None = None,
    ) -> dict:
        msg: dict = {
            "cd_schema": "cd.agent.message/0",
            "id": ids.new_id("msg"),
            "thread_id": thread_id or ids.new_id("thr"),
            "from": sender,
            "to": recipient,
            "kind": kind,
            "created_at": ids.now(),
            "body": body,
        }
        if reply_to:
            msg["reply_to"] = reply_to
        if data_class:
            msg["data_class"] = data_class
        errors = list(validator(SCHEMA).iter_errors(msg))
        if errors:
            e = errors[0]
            raise MessageError(f"invalid message {'/'.join(map(str, e.absolute_path))}: {e.message}")
        return msg

    def insert(self, connection, msg):
        """Insert a prepared message in the caller's transaction. Notify only AFTER commit."""
        connection.execute(
            "INSERT INTO messages (id,thread_id,reply_to,sender,recipient,kind,task_id,created_at,doc) VALUES (?,?,?,?,?,?,?,?,?)",
            (msg["id"], msg["thread_id"], msg.get("reply_to"), msg["from"], msg["to"], msg["kind"],
             msg["body"].get("task_id"), msg["created_at"], dumps(msg)))

    def post(self, **kwargs):
        msg = self.prepare(**kwargs)
        with self.db.tx() as connection:
            self.insert(connection, msg)
        self.notify(msg["to"])
        return msg

    def next_for(self, recipient: str, *, kinds: tuple[str, ...] | None = None) -> dict | None:
        """Oldest undelivered message for `recipient` (optionally only some kinds)."""
        sql = "SELECT doc FROM messages WHERE recipient = ? AND delivered_at IS NULL"
        params: list = [recipient]
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            params.extend(kinds)
        # A computer action waits for its guardian's approval: those tasks go before everything else.
        row = self.db.one(sql + " ORDER BY (json_extract(doc, '$.body.approval_of') IS NULL), seq LIMIT 1", tuple(params))
        return json.loads(row["doc"]) if row else None

    def mark_delivered(self, message_id: str) -> None:
        with self.db.tx() as c:
            c.execute("UPDATE messages SET delivered_at = ? WHERE id = ?", (ids.now(), message_id))

    async def wait(self, recipient: str, timeout: float) -> None:
        """Sleep until a message is posted for `recipient` (or timeout, to notice other processes' writes)."""
        self.bind_loop(asyncio.get_running_loop())
        ev = self._events[recipient]
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except TimeoutError:
            pass
        ev.clear()

    def list(self, *, recipient: str | None = None, thread_id: str | None = None, task_id: str | None = None,
             after_seq: int = 0, limit: int = 200) -> list[dict]:
        where, params = ["seq > ?"], [after_seq]
        for col, val in (("recipient", recipient), ("thread_id", thread_id), ("task_id", task_id)):
            if val:
                where.append(f"{col} = ?")
                params.append(val)
        rows = self.db.query(f"SELECT seq, doc FROM messages WHERE {' AND '.join(where)} ORDER BY seq LIMIT ?", (*params, limit))
        return [{**json.loads(r["doc"]), "_seq": r["seq"]} for r in rows]
