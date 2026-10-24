#!/usr/bin/env python3
"""
Metacognition pre-hook — Claude Code UserPromptSubmit.

Fires on every user prompt. Detects correction signals (neg/pos), weakens
metacognition entries on correction / strengthens on confirmation, and tracks
active curiosities against the prompt. Silent (exit 0, no context injection) —
it only updates the agent's own metacognition.json.

Placed in the metacognition skill's scripts/ dir so HOME = the skill dir and the
DB resolves to <skill>/memory/metacognition.json (the existing per-agent store).
Logic ported from Mavis McVail's mc-pre.py; only the hook I/O is Claude-native.
"""
import json, os, sys, re
from datetime import datetime

HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the skill dir
DB_PATH = os.path.join(HOME, "memory", "metacognition.json")

NEG = [
    r"\bwrong\b", r"\bno\b", r"\bthat's not right\b", r"\bincorrect\b",
    r"\byou're hallucinating\b", r"\bthat didn't happen\b",
    r"\bstop\b", r"\bwait\b", r"\bthat's not what\b",
    r"\bnot quite\b", r"\bnot exactly\b", r"\bactually\b",
    r"\bi meant\b", r"\bi said\b", r"\bno,?\b",
]
POS = [
    r"\byes\b", r"\byeah\b", r"\bexactly\b", r"\bperfect\b",
    r"\bcorrect\b", r"\bthat's right\b", r"\bgood\b",
    r"\bthat's it\b", r"\bnailed it\b", r"\bbrilliant\b",
]


def load_db():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"version": 1, "entries": [], "feedback_log": [],
            "meta": {"total_decisions": 0, "total_corrections": 0, "accuracy_by_domain": {}}}


def save_db(db):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DB_PATH)


def active_entries(db, entry_type=None, limit=10, min_s=0.15):
    out = [e for e in db.get("entries", [])
           if not e.get("resolved") and e.get("strength", 0) >= min_s
           and (entry_type is None or e.get("type") == entry_type)]
    out.sort(key=lambda e: e.get("strength", 0), reverse=True)
    return out[:limit]


def feedback(db, direction, context, eids):
    now = datetime.now().isoformat()
    db.setdefault("feedback_log", []).append(
        {"time": now, "direction": direction, "context": context, "entry_ids": eids})
    if direction < 0:
        db.setdefault("meta", {})["total_corrections"] = db["meta"].get("total_corrections", 0) + 1
    targets = [e for e in db.get("entries", []) if e.get("id") in (eids or [])]
    for e in targets:
        e.setdefault("feedback", []).append({"time": now, "direction": direction, "context": context})
        e["strength"] = (min(1.0, e.get("strength", 0.5) + 0.15) if direction > 0
                         else max(0.05, e.get("strength", 0.5) - 0.25))
        e["last_touched"] = now
    return len(targets)


def scan(text):
    t = text.lower()
    n = sum(1 for s in NEG if re.search(s, t, re.I))
    p = sum(1 for s in POS if re.search(s, t, re.I))
    return n, p


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)
    # Claude Code UserPromptSubmit provides the prompt directly.
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    if not prompt:
        sys.exit(0)

    db = load_db()
    neg, pos = scan(prompt)

    if neg >= 2 or (neg >= 1 and pos == 0):
        eids = [e["id"] for e in active_entries(db, limit=5)]
        feedback(db, -1, f"neg={neg} pos={pos}", eids)
    elif pos >= 2:
        eids = [e["id"] for e in active_entries(db, limit=5)]
        feedback(db, +1, f"pos={pos}", eids)

    # curiosity reinforcement
    pl = prompt.lower()
    for c in active_entries(db, "curiosity", limit=3):
        kw = [w for w in c.get("content", "").lower().split() if len(w) > 4]
        if any(k in pl for k in kw):
            c.setdefault("evidence", []).append(f"pre: {prompt[:80]}")
            lc = c.get("lifecycle")
            c["lifecycle"] = "active" if lc in (None, "born") else ("evolving" if lc == "active" else lc)
            c["reinforcements"] = c.get("reinforcements", 1) + 1
            c["last_touched"] = datetime.now().isoformat()

    save_db(db)
    sys.exit(0)  # silent — no context injection


if __name__ == "__main__":
    main()
