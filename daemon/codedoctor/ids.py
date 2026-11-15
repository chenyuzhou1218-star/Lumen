"""Id and timestamp helpers shared by every component."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_lock = threading.Lock()
_last = (0, 0)


def ulid() -> str:
    """Monotonic ULID: ids created later in this process always sort later."""
    global _last
    with _lock:
        ms = int(time.time() * 1000)
        last_ms, last_rand = _last
        if ms <= last_ms:
            ms, rand = last_ms, last_rand + 1
        else:
            rand = int.from_bytes(os.urandom(10), "big")
        _last = (ms, rand)
    n = (ms << 80) | (rand & ((1 << 80) - 1))
    return "".join(_CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(26)))


def new_id(prefix: str) -> str:
    return f"{prefix}_{ulid()}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
