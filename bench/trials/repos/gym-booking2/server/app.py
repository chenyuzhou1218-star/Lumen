"""HTTP routes (standard library JSON server)."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server import bookings, classes, db

ROUTES = {
    ("GET", "/api/class"): lambda q: {**classes.get(q["id"]), "remaining": classes.remaining(q["id"])},
    ("GET", "/api/credits"): lambda q: {"credits": db.credits.get(q["user"], 0)},
    ("POST", "/api/book"): lambda b: bookings.book(b["user"], b["class_id"]),
    ("POST", "/api/cancel"): lambda b: bookings.cancel(b["booking_id"]),
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        self._dispatch("GET", path, dict(p.split("=", 1) for p in query.split("&") if "=" in p))

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        self._dispatch("POST", self.path, body)

    def _dispatch(self, method, path, arg):
        fn = ROUTES.get((method, path))
        if fn is None:
            return self._send(404, {"error": "not found"})
        try:
            self._send(200, fn(arg))
        except Exception as e:
            self._send(400, {"error": str(e)})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8081), Handler).serve_forever()
