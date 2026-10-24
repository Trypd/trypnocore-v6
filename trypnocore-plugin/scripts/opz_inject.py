"""opz-memory auto-injection helper (Windows side of the CC-WSL hook).

Reads one user-prompt line from stdin, asks the OmegaPrimeZero chat server
for the associative trinket blocks (time, curated memories, reminders,
curator status), and prints them to stdout. Claude Code's UserPromptSubmit
hook adds that stdout to the model's context.

Three sources merge into the block:
  1. the agent's own pool  (OPZ_POOL via WSLENV, else resolved from PWD via registry)
  2. the `collective` pool (channel events: #lobby/#mud/#ops, kanban moves)
  3. the tail of the agent's monologue.md (Jaynesian narrator, last entry)

Any failure exits 0 silently — a down server must never block a prompt.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tryp_identity import resolve

BASE = "http://127.0.0.1:8787"
COLLECTIVE = "collective"
MONOLOGUE_TAIL = 600  # last narrator entry, roughly


def _context(pool: str, line: str) -> list[str]:
    tail = f"line={urllib.parse.quote(line, safe='')}&pool={urllib.parse.quote(pool, safe='')}"
    try:
        with urllib.request.urlopen(f"{BASE}/memory/context?{tail}", timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    return data.get("sections") or []


def _monologue_tail(folder: str) -> str:
    path = Path(folder) / "monologue.md"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    return text[-MONOLOGUE_TAIL:] if text else ""


def main() -> None:
    line = sys.stdin.read().strip()
    if not line:
        return
    pool = os.environ.get("OPZ_POOL", "").strip()
    cwd = os.environ.get("TRYPD_CWD", "") or os.environ.get("PWD", "")
    agent = resolve(cwd)
    folder = agent.get("folder", "") if agent else ""
    if not pool and agent:
        pool = agent.get("pool") or ""

    sections: list[str] = []
    if pool:
        sections += _context(pool, line)
    sections += _context(COLLECTIVE, line)
    if folder:
        mono = _monologue_tail(folder)
        if mono:
            sections.append(f"[trinket monologue]\n{mono}")
    if sections:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.write("\n\n".join(sections) + "\n")


if __name__ == "__main__":
    main()
