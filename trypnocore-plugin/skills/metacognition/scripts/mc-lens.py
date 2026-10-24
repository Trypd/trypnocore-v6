#!/usr/bin/env python3
"""
Metacognition lens injector — Claude Code UserPromptSubmit (OpenWolf bake 2026-07-08;
turn-conditional rewrite 2026-07-16 per Igor's boot-QA).

Companion to mc-pre.py, deliberately separate: mc-pre is the SILENT Hebbian
bookkeeper (never modified); this one is the VISIBLE half of the per-turn autofire.
It compiles the agent's strongest RELEVANT lens entries and prints them
(UserPromptSubmit stdout is injected into context).

Two things the old version got wrong (Igor's cockpit report):
  1. WALLPAPER — it ranked purely by strength, so the same 0.55 item re-injected
     every turn regardless of what the turn was about. Now it reads THIS turn's
     prompt (from the hook's stdin payload) and ranks relevant items first;
     overrides (safety guardrails) still always surface.
  2. MID-CLAUSE TRUNCATION — it hard-cut at 120 chars ("...comes down and"). Now
     it cuts at a word boundary and marks the elision.

Optional-if-installed: absent/empty/weak DB -> prints nothing, exit 0. ASCII-only
output (Windows console). Max 6 lines. DB resolves skill-dir-relative.
"""
import json, os, re, sys

HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(HOME, "memory", "metacognition.json")

MIN_STRENGTH = 0.55
TAGS = {"override": "MUST", "protection": "KEEP", "perception": "SEE", "self_obs": "SELF", "curiosity": "ASK"}
STOP = {"this", "that", "with", "from", "have", "will", "your", "they", "them", "then", "than",
        "what", "when", "which", "into", "about", "just", "like", "some", "make", "does", "done"}


def turn_words():
    """Words from THIS turn's prompt, so the lens can adapt. UserPromptSubmit passes
    a JSON payload on stdin; be liberal about shape and never block on it."""
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    except Exception:
        raw = ""
    prompt = ""
    if raw:
        try:
            obj = json.loads(raw)
            prompt = obj.get("prompt") or obj.get("user_prompt") or obj.get("message") or raw
        except Exception:
            prompt = raw
    return {w for w in re.findall(r"[a-z]{4,}", prompt.lower()) if w not in STOP}


def clip(text, n=112):
    """Truncate at a word boundary, not mid-clause."""
    t = str(text).replace("\n", " ").strip()
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0]
    return cut + " ..."


def main():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
    except Exception:
        sys.exit(0)

    entries = [e for e in db.get("entries", [])
               if not e.get("resolved") and e.get("strength", 0) >= MIN_STRENGTH]
    if not entries:
        sys.exit(0)

    words = turn_words()

    def relevance(e):
        c = set(re.findall(r"[a-z]{4,}", str(e.get("content", "")).lower()))
        return len(c & words)

    # Rank: overrides (safety guardrails) always float up; then by turn-relevance;
    # then by strength. This is what kills the wallpaper — a turn about topic X now
    # surfaces X-relevant keeps, not the same static 0.55 item every time.
    def key(e):
        return (
            1 if e.get("type") == "override" else 0,
            relevance(e),
            e.get("strength", 0),
        )
    entries.sort(key=key, reverse=True)

    picked, seen_types = [], {}
    for e in entries:  # max 2 per type, 5 total
        t = e.get("type", "?")
        if seen_types.get(t, 0) >= 2:
            continue
        seen_types[t] = seen_types.get(t, 0) + 1
        picked.append(e)
        if len(picked) >= 5:
            break

    lines = ["[metacog-lens | this turn]"]
    for e in picked:
        tag = TAGS.get(e.get("type"), "NOTE")
        mark = "*" if relevance(e) else ""  # * = relevant to this turn's prompt
        lines.append(f"  {tag}{mark}: {clip(e.get('content', ''))} ({e.get('strength', 0):.2f})")
    out = "\n".join(lines) + "\n"
    try:
        sys.stdout.write(out.encode("ascii", "replace").decode("ascii"))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
