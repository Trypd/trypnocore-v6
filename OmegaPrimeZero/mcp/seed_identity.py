"""Seed per-agent identity pools: soul.md + bootstrap md + AGENTS.md sections.

Each identity document is split on markdown section headers; each section
becomes one atom in the agent's `identity-<slug>` pool. The pool is read-only
by convention — nothing in the runtime writes to it after seeding; re-seed
after identity docs change.

Run with the OPZ server UP:  python mcp/seed_identity.py [slug ...]
No args = all agents in the registry. Pointer-deduped; safe to re-run.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8787"
REGISTRY = Path(r"C:\Trypnocore\fleet\fleet-registry.json")
MAX_SECTION_CHARS = 600

# Sections that carry identity weight. Noise (file trees, logs) is skipped.
SKIP_HEADS = re.compile(r"file tree|directory|log$|changelog|appendix", re.IGNORECASE)


def _sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (header, body) pairs on # / ## / ### lines."""
    parts = re.split(r"^(#{1,3} .+)$", text, flags=re.MULTILINE)
    out = []
    if parts and parts[0].strip():
        out.append(("(preamble)", parts[0].strip()))
    for i in range(1, len(parts), 2):
        head = parts[i].lstrip("#").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if SKIP_HEADS.search(head):
            continue
        out.append((head, body))
    return [(h, b) for h, b in out if b]


def _atom(slug: str, doc: str, head: str, body: str) -> str:
    return f"[identity {slug} · {doc} · {head}]\n{body[:MAX_SECTION_CHARS]}"


def _remember(pool: str, claim: str, evidence: str) -> bool:
    body = json.dumps({"line": f"remember that {claim}", "pool": pool}).encode()
    req = urllib.request.Request(
        f"{BASE}/memory/remember", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read()).get("remembered", 0) > 0
    except Exception:
        return False


def seed_agent(agent: dict) -> int:
    slug = agent["slug"]
    if slug == "memory":
        return 0
    folder = Path(agent["folder"])
    pool = f"identity-{agent['pool']}"
    docs = [d for d in agent.get("bootstrap_docs", []) if (folder / d).is_file()]
    written = 0
    for doc_name in docs:
        text = (folder / doc_name).read_text(encoding="utf-8", errors="replace")
        for head, body in _sections(text):
            claim = _atom(slug, doc_name, head, body)
            if _remember(pool, claim, f"identity seed from {doc_name} §{head}"):
                written += 1
    return written


def main() -> None:
    agents = json.loads(REGISTRY.read_text(encoding="utf-8"))["agents"]
    wanted = set(sys.argv[1:])
    total = 0
    for agent in agents:
        if wanted and agent["slug"] not in wanted:
            continue
        n = seed_agent(agent)
        if n:
            print(f"{agent['slug']:38s} +{n:3d} identity atoms")
        total += n
    print(f"TOTAL: {total} identity atoms seeded")


if __name__ == "__main__":
    main()
