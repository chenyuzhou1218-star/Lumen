"""Run the service (Daemon) on its own asyncio thread inside a desktop process.

The window calls commands through `run` (executed on the service loop, so agent
wake-ups are immediate) and reads the database directly (it is thread-safe).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading

from codedoctor.agents.daemon import Daemon


class Backend:
    def __init__(self, cfg, poll_s: float = 1.0):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="codedoctor-service", daemon=True).start()
        self.daemon: Daemon = self._call(self._start(cfg, poll_s), timeout=120)

    async def _start(self, cfg, poll_s: float) -> Daemon:
        d = Daemon(cfg, poll_s=poll_s)
        try:
            await d.start()
        except BaseException:
            await d.s.aclose()
            raise
        return d

    def _call(self, coro, timeout: float = 30):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    RUN_WAIT_S = 30  # how long the window waits for a command before it says so

    def run(self, fn, *args, **kw):
        """Run a synchronous command on the service loop. When the wait runs out, the command is cancelled if it has
        not started yet: a submit reported as failed must not create its task later (Haiku check item 5)."""
        gave_up = threading.Event()

        async def wrapper():
            if gave_up.is_set():  # the window stopped waiting before the loop got to it: do nothing
                return None
            return fn(*args, **kw)
        future = asyncio.run_coroutine_threadsafe(wrapper(), self.loop)
        try:
            return future.result(self.RUN_WAIT_S)
        except concurrent.futures.TimeoutError:
            gave_up.set()
            future.cancel()
            raise TimeoutError(f"the service did not answer within {self.RUN_WAIT_S} s") from None

    def close(self) -> None:
        try:
            self._call(self.daemon.stop(), timeout=30)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
