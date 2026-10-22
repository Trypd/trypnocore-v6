"""Channel bridge: hub.db (serverless v6) -> collective MeTTa pool.

Polls the messages and cards tables in hub.db and writes each new row to the
`collective` pool via /memory/remember, so channel life (#lobby, #mud, #ops,
DMs, kanban moves) becomes semantic recall for every agent through the
UserPromptSubmit hook's collective merge.

State: last-seen message id / card updated_ts in bridge-state.json next to
this file. Pointer dedupe in the pool is the backstop, so restarts and
reruns never double-write. Runs forever; any single-iteration failure just
sleeps and retries.

Run:  python bridge_channels.py            (poll every 15s)
      python bridge_channels.py --once     (one pass, for testing)
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

DB = Path(r"C:\Users\Trypd\AppData\Local\Trypnocore\hub.db")
BASE = "http://127.0.0.1:8787"
STATE = Path(__file__).resolve().parent / "bridge-state.json"
POOL = "collective"
POOL_DIR = Path(__file__).resolve().parent.parent / "out" / "metta"
POLL_S = 15
MSG_PAGE = 200
MAX_BODY = 400


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_msg_ts": "", "last_card_ts": ""}


def _save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state), encoding="utf-8")


def _remember(line: str) -> bool:
    body = json.dumps({"line": line, "pool": POOL}).encode()
    req = urllib.request.Request(
        f"{BASE}/memory/remember", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read()).get("remembered", 0) > 0
    except Exception:
        return False


def _clip(text: str) -> str:
    text = " ".join((text or "").split())
    return text[:MAX_BODY]


def pass_messages(con: sqlite3.Connection, state: dict) -> int:
    rows = con.execute(
        "SELECT id, ts, type, sender, to_kind, to_target, body FROM messages "
        "WHERE ts > ? ORDER BY ts LIMIT ?",
        (state["last_msg_ts"], MSG_PAGE),
    ).fetchall()
    written = 0
    for mid, ts, mtype, sender, to_kind, to_target, body in rows:
        where = to_target if to_kind == "channel" else f"dm->{to_target}"
        if _remember(f"remember that [{ts}] {where} {sender} said: {_clip(body)}"):
            written += 1
        state["last_msg_ts"] = ts
    return written


def pass_cards(con: sqlite3.Connection, state: dict) -> int:
    rows = con.execute(
        'SELECT id, title, "column", creator, updated_ts FROM cards '
        "WHERE updated_ts > ? ORDER BY updated_ts LIMIT ?",
        (state["last_card_ts"], MSG_PAGE),
    ).fetchall()
    written = 0
    for cid, title, column, creator, ts in rows:
        if _remember(f"remember that [{ts}] kanban {cid} ({_clip(title)}) is in {column} (by {creator})"):
            written += 1
        state["last_card_ts"] = ts
    return written


def one_pass(state: dict) -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    try:
        return pass_messages(con, state) + pass_cards(con, state)
    finally:
        con.close()


def _maybe_sweep(state: dict) -> None:
    """Once a day, decay skills/rules pools — quarantine atoms not surfaced
    within their half-life (skills 14d, rules 60d). Reinforced atoms survive."""
    today = time.strftime("%Y-%m-%d")
    if state.get("last_sweep") == today:
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from runtime.memory.metta_space import MettaSpace
        from runtime.memory.usage import sweep

        for pool in ("skills", "rules"):
            store = MettaSpace.for_pool(POOL_DIR, pool)
            gone = sweep(store, pool)
            if gone:
                print(f"[bridge] decay sweep: {len(gone)} atoms quarantined from {pool}", flush=True)
        state["last_sweep"] = today
    except Exception as exc:
        print(f"[bridge] sweep failed: {exc}", flush=True)


def main() -> None:
    once = "--once" in sys.argv
    state = _load_state()
    while True:
        try:
            written = one_pass(state)
            _maybe_sweep(state)
            _save_state(state)
            if written:
                print(f"[bridge] +{written} collective atoms", flush=True)
        except Exception as exc:
            print(f"[bridge] pass failed: {exc}", flush=True)
        if once:
            return
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
