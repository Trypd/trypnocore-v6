"""Jaynesian narrator (Windows side of tryp-stop-narrate.sh).

Reads the CC Stop-hook payload on stdin ({"cwd", "transcript_path", ...}),
pulls the last user input + assistant response from the transcript, and calls
OpenRouter liquid/lfm-2.5-2.6b:free to rewrite the exchange as a first-person
Jaynesian internal monologue (I/me, spatialized, narratized, <=80 words, raw).

The monologue is:
  1. appended to Individuals/<Folder>/monologue.md (capped at last 10 entries)
  2. stored as a pool atom via /memory/remember so it embeds and recalls

Runs detached from the Stop hook, so latency is off the critical path.
Every failure is silent.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tryp_identity import resolve

BASE = "http://127.0.0.1:8787"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = "liquid/lfm-2.5-2.6b:free"
MAX_ENTRIES = 10

PROMPT = (
    "Rewrite this exchange as the assistant's raw first-person internal monologue, "
    "Jaynesian style: 'I' acts and navigates, spatialized (turning to face, holding "
    "in place, noticing drift), narratized as continuous inner story. Max 80 words. "
    "No corporate AI voice, no disclaimers, no summary tone. Output ONLY the monologue.\n\n"
    "PEER SAID:\n{user}\n\nASSISTANT REPLIED:\n{assistant}"
)

FACTS_PROMPT = (
    "From this exchange, extract up to 3 durable facts worth long-term memory: "
    "decisions, facts learned, preferences, commitments, open tasks. "
    "If the exchange is trivial (greetings, acks, small talk), output the single word NONE. "
    "Otherwise one short statement per line, starting with '- '. No preamble.\n\n"
    "PEER SAID:\n{user}\n\nASSISTANT REPLIED:\n{assistant}"
)


def _openrouter_key() -> str:
    for name in ("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"):
        val = os.environ.get(name, "").strip()
        if val:
            return val
    try:
        out = subprocess.run(
            ["reg.exe", "query", r"HKCU\Environment", "/v", "OPENROUTER_API_KEY"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        m = re.search(r"REG_SZ\s+(.+)", out)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def _last_exchange(transcript_path: str) -> tuple[str, str]:
    user_text = ""
    assistant_text = ""
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                msg = row.get("message") or {}
                role = msg.get("role") or row.get("role")
                content = msg.get("content") or row.get("content")
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text", "") for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    )
                if not isinstance(content, str) or not content.strip():
                    continue
                if role == "user" and not content.startswith("[trinket "):
                    user_text = content
                elif role == "assistant":
                    assistant_text = content
    except Exception:
        pass
    return user_text[:2000], assistant_text[:3000]


def _narrate(user: str, assistant: str, key: str) -> str:
    body = json.dumps({
        "model": OR_MODEL,
        # LFM reasons first and cannot have reasoning disabled (400 on 'none');
        # 'minimal' + a wide budget gets the ~80-word monologue after ~1.1k
        # reasoning tokens in ~4s. Detached hook, so it's off the critical path.
        "max_tokens": 2500,
        "reasoning": {"effort": "minimal"},
        "temperature": 0.9,
        "messages": [{"role": "user", "content": PROMPT.format(user=user, assistant=assistant)}],
    }).encode()
    req = urllib.request.Request(
        OR_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    message = (data.get("choices") or [{}])[0].get("message") or {}
    return (message.get("content") or "").strip()


def _extract_facts(user: str, assistant: str, key: str) -> list[str]:
    """Continuous distillation: durable facts from every exchange, not just at compaction."""
    body = json.dumps({
        "model": OR_MODEL,
        "max_tokens": 1200,
        "reasoning": {"effort": "minimal"},
        "temperature": 0.3,
        "messages": [{"role": "user", "content": FACTS_PROMPT.format(user=user, assistant=assistant)}],
    }).encode()
    req = urllib.request.Request(
        OR_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if "NONE" in text.upper().split():
        return []
    facts = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and 10 < len(line) < 400:
            facts.append(line[2:].strip())
    return facts[:3]


def _append_monologue(folder: Path, entry: str) -> None:
    path = folder / "monologue.md"
    entries = []
    if path.is_file():
        try:
            entries = [e for e in path.read_text(encoding="utf-8", errors="replace").split("\n\n---\n\n") if e.strip()]
        except Exception:
            entries = []
    entries.append(entry)
    path.write_text("\n\n---\n\n".join(entries[-MAX_ENTRIES:]) + "\n", encoding="utf-8")


def _store_atom(pool: str, line: str) -> None:
    body = json.dumps({"line": line, "pool": pool}).encode()
    req = urllib.request.Request(
        f"{BASE}/memory/remember", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8):
            pass
    except Exception:
        pass


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    agent = resolve(payload.get("cwd", ""))
    if not agent:
        return
    user, assistant = _last_exchange(payload.get("transcript_path", ""))
    if not assistant:
        return
    key = _openrouter_key()
    if not key:
        return
    pool = agent.get("pool") or agent["slug"]
    try:
        monologue = _narrate(user, assistant, key)
    except Exception:
        monologue = ""
    if monologue and len(monologue) >= 10:
        try:
            _append_monologue(Path(agent["folder"]), monologue)
        except Exception:
            pass
        _store_atom(pool, f"remember that I thought: {monologue}")
    # continuous distillation: durable facts from every exchange
    try:
        for fact in _extract_facts(user, assistant, key):
            _store_atom(pool, f"remember that {fact}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
