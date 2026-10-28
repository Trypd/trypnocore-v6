"""Small, dependency-free memory HTTP service for solo Linux/WSL agents.

Compatible with the OPZ endpoints used by the plugin and harness-neutral agents.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recall import choose_memories
from sql_space import SqlSpace, check_pool

REMEMBER = re.compile(r"^\s*remember\b[:\s,-]*(.*)$", re.IGNORECASE | re.DOTALL)
REMIND = re.compile(r"^\s*remind\s+me\b[:\s,-]*(.*)$", re.IGNORECASE | re.DOTALL)


def explicit_notes(line: str) -> list[str]:
    if match := REMIND.match(line):
        text = match.group(1).strip()
        return [f"reminder: {text}"] if text else []
    if match := REMEMBER.match(line):
        text = match.group(1).strip()
        if text.lower().startswith("that "):
            text = text[5:].strip()
        return [text] if text else []
    return []


def store(pool: str) -> SqlSpace:
    return SqlSpace.for_pool(pool)


def pointer(claim: str) -> str:
    return "explicit-" + hashlib.sha256(claim.encode("utf-8")).hexdigest()[:16]


class Proof:
    def __init__(self, claim: str):
        self.claim = claim
        self.pointer = pointer(claim)
        self.evidence = "explicit"


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _pool(self, query: dict) -> str:
        try:
            return check_pool(query.get("pool", ["default"])[0])
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            pool = self._pool(query)
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        if parsed.path == "/v1/models":
            return self._json(200, {"object": "list", "data": [{"id": "trypnocore-memory", "object": "model", "owned_by": "trypnocore"}]})
        if parsed.path == "/memory/atoms":
            claims = store(pool).claims()
            return self._json(200, {"atoms": claims, "count": len(claims), "pool": pool})
        if parsed.path == "/memory/context":
            claims = store(pool).claims()
            line = query.get("line", [""])[0]
            memories = choose_memories(claims, line, pool=pool)
            reminders = [c[len("reminder: "):] for c in claims if c.startswith("reminder: ")]
            sections = [f"[trinket time]\n{datetime.now().astimezone().isoformat(timespec='seconds')}"]
            if memories:
                sections.append("[trinket memory]\n" + "\n".join(memories))
            if reminders:
                sections.append("[trinket reminders]\n" + "\n".join(reminders[-8:]))
            sections.append(f"[trinket curator]\nmetta atoms: {len(claims)} · pool: {pool} · backend: sqlite")
            return self._json(200, {"sections": sections, "pool": pool})
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/memory/remember":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            line = str(payload.get("line", ""))
            pool = check_pool(str(payload.get("pool") or "default"))
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})
        if not line.strip():
            return self._json(400, {"error": "line is required"})
        notes = explicit_notes(line)
        if not notes:
            return self._json(200, {"remembered": 0, "pool": pool})
        target = store(pool)
        for claim in notes:
            target.remember(Proof(claim))
        return self._json(200, {"remembered": len(notes), "atoms": target.count(), "pool": pool})

    def log_message(self, *_args) -> None:
        pass


def main() -> None:
    port = int(os.environ.get("OPZ_CHAT_PORT", "8787"))
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"trypnocore memory listening on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
