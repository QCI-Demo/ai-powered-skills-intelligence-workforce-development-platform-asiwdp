#!/usr/bin/env python3
"""Minimal Skills API stub for CI Newman / k6 smoke runs.

Serves enough of the Skills Framework surface for pipeline health checks and
skill-lookup load tests. Not a production mock — synthetic data only, no PII.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


HOST = os.getenv("MOCK_HOST", "0.0.0.0")
PORT = int(os.getenv("MOCK_PORT", "8080"))

SKILLS_PAYLOAD = {
    "items": [
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "name": "Python",
            "category": "engineering",
            "status": "active",
            "version": "1",
        }
    ],
    "total": 1,
    "offset": 0,
    "limit": 50,
}


class SkillsHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        # Keep CI logs quiet; avoid echoing Authorization headers.
        return

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _unauthorized(self) -> None:
        self._json(401, {"error": "unauthorized", "message": "Bearer token required"})

    def _require_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or len(auth) < 16:
            self._unauthorized()
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path in ("/health", "/api/v1/health"):
            self._json(200, {"status": "ok"})
            return

        if path in ("/skills", "/api/v1/skills"):
            if not self._require_auth():
                return
            self._json(200, SKILLS_PAYLOAD)
            return

        self._json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length:
            self.rfile.read(length)

        if not self._require_auth():
            return

        if path.endswith("/taxonomy/import") or path.endswith("/skills"):
            self._json(
                201,
                {
                    "id": "00000000-0000-4000-8000-000000000099",
                    "status": "accepted",
                    "imported": 0,
                    "errors": [],
                },
            )
            return

        self._json(404, {"error": "not_found", "path": path})

    def do_PATCH(self) -> None:  # noqa: N802
        self.do_POST()

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        self._json(204, {})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), SkillsHandler)
    print(f"mock skills api listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
