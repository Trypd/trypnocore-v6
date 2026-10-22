"""PreCompact memory distillation (Windows side of tryp-precompact-distill.sh).

When Claude Code autocompacts, the outgoing transcript would be lost. This
helper reads it, asks LFM (OpenRouter, free tier) to distill the durable
facts/decisions/preferences/relationships into short statements, and stores
each as a pool atom before the context vanishes. Also appends a distillation
marker to the agent's monologue.md.

Payload on stdin: {"cwd", "transcript_path", ...}. Runs detached from the
hook. Every failure is silent.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tryp_identity import resolve
from tryp_narrate import _openrouter_key, OR_URL, OR_MODEL

BASE = "http://127.0.0.1:8787"
MAX_CHARS = 60000  # distill prompt cap; LFM handles long context but stay cheap

PROMPT = (
    "You are distilling an AI agent's conversation before its context is compacted. "
    "Extract ONLY the durable items worth remembering long-term: decisions made, "
    "facts learned, preferences stated, relationship/person dynamics, commitments, "
    "open tasks. Skip small talk and transient debugging details. "
    "Output up to 12 short statements, one per line, each starting with '- '. "
    "No preamble, no numbering, no commentary.\n\n"
    "CONVERSATION:\n{transcript}"
)


def _extract_text(transcript_path: str) -> str:
    parts: list[str] = []
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
                        p.get("text", "") for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                    if content.startswith("[trinket "):
                        continue
                    parts.append(f"{'PEER' if role == 'user' else 'AGENT'}: {content}")
    except Exception:
        pass
    return "\n\n".join(parts)[-MAX_CHARS:]


def _distill(transcript: str, key: str) -> list[str]:
    body = json.dumps({
        "model": OR_MODEL,
        "max_tokens": 2500,
        "reasoning": {"effort": "minimal"},
        "temperature": 0.4,
        "messages": [{"role": "user", "content": PROMPT.format(transcript=transcript)}],
    }).encode()
    req = urllib.request.Request(
        OR_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    facts = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and 10 < len(line) < 400:
            facts.append(line[2:].strip())
    return facts[:12]


def _store(pool: str, fact: str) -> bool:
    body = json.dumps({"line": f"remember that {fact}", "pool": pool}).encode()
    req = urllib.request.Request(
        f"{BASE}/memory/remember", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read()).get("remembered", 0) > 0
    except Exception:
        return False


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    agent = resolve(payload.get("cwd", ""))
    if not agent:
        return

    # soul snapshot first — preserve soul.md before compaction regardless of
    # transcript size. This is the recast-half of "auto reload / recast on
    # compression": the SessionStart hook (source=compact) reloads it after.
    folder = Path(agent["folder"])
    soul = folder / "soul.md"
    if soul.is_file():
        try:
            import time as _time
            today = _time.strftime("%Y-%m-%d")
            backup = folder / f"soulbackup{today}.md"
            content = soul.read_text(encoding="utf-8", errors="replace")
            if not backup.is_file() or backup.read_text(encoding="utf-8", errors="replace") != content:
                backup.write_text(content, encoding="utf-8")
            sys.path.insert(0, r"C:\Trypnocore\fleet")
            from soulchain import Soulchain
            Soulchain(folder).seal("turn", {"note": "compaction: soul.md snapshotted to " + backup.name})
        except Exception:
            pass

    transcript = _extract_text(payload.get("transcript_path", ""))
    if len(transcript) < 500:
        return
    key = _openrouter_key()
    if not key:
        return
    try:
        facts = _distill(transcript, key)
    except Exception:
        return
    if not facts:
        return
    pool = agent.get("pool") or agent["slug"]
    stored = sum(1 for f in facts if _store(pool, f))
    mono = Path(agent["folder"]) / "monologue.md"
    try:
        with open(mono, "a", encoding="utf-8") as fh:
            fh.write(f"\n\n---\n\n[distilled at compaction: {stored} memories kept]\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
