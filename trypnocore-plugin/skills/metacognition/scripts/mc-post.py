#!/usr/bin/env python3
"""
Metacognition post-hook — Claude Code Stop.

Fires when the agent finishes a turn. Records the turn, and scans the agent's
OWN last response (from the transcript) for self-correction / hesitation markers
— the "noticed myself reconsidering" signal — incrementing a self-correction
counter. Silent (exit 0). DB resolves to <skill>/memory/metacognition.json.
"""
import json, os, sys, re
from datetime import datetime

HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(HOME, "memory", "metacognition.json")

SELF_CORR = [
    r"let me reconsider", r"i was wrong", r"correction:", r"on second thought",
    r"actually,? (i|the|that|it)", r"that's not right", r"i need to (re|back)",
    r"scratch that", r"i mis(read|judged|understood)",
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


def last_assistant_text(transcript_path):
    text = ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if o.get("type") == "assistant" or o.get("role") == "assistant" \
                        or (isinstance(o.get("message"), dict) and o["message"].get("role") == "assistant"):
                    msg = o.get("message", o)
                    c = msg.get("content")
                    if isinstance(c, list):
                        t = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                        if t:
                            text = t
                    elif isinstance(c, str) and c:
                        text = c
    except Exception:
        pass
    return text


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    db = load_db()
    meta = db.setdefault("meta", {})
    meta["total_decisions"] = meta.get("total_decisions", 0) + 1
    meta["last_turn"] = datetime.now().isoformat()

    tp = payload.get("transcript_path")
    if tp and os.path.exists(tp):
        txt = last_assistant_text(tp).lower()
        if txt and any(re.search(s, txt) for s in SELF_CORR):
            meta["self_corrections"] = meta.get("self_corrections", 0) + 1
            meta["last_self_correction"] = datetime.now().isoformat()

    save_db(db)
    sys.exit(0)


if __name__ == "__main__":
    main()
