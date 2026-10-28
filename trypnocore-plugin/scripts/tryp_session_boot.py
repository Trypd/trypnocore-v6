"""SessionStart personality loader (Windows side of tryp-session-start.sh).

Reads the CC hook payload on stdin ({"cwd", "source", ...}), resolves the
owning agent via tryp_identity, and prints the boot block:

  1. identity + lane + pool
  2. full bootstrap assembly — CORE.md header, newest soulbackup, soul.md,
     the eponymous bootstrap md, tasks.md — so boot needs no manual reread
  3. soulchain: epoch drift report (silent identity-doc edits) + last N rings
  4. one semantic memory page from the OPZ server

source=="compact" re-fires this hook after autocompaction, which makes the
same block the reload-and-recast path: identity and chain come back into
context automatically after every compaction.

Fails silent — a boot must never error out.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tryp_identity import resolve

BASE = os.environ.get("OPZ_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
SOUL_CAP = 1200   # soul.md casts are short by design; hard cap anyway
CORE_CAP = 1500   # roster header only, not the whole org chart
BACKUP_CAP = 900  # newest soulbackup, capped
TASKS_CAP = 600
BOOTSTRAP_CAP = 1200


def _memory_page(pool: str, line: str) -> str:
    tail = f"line={urllib.parse.quote(line, safe='')}&pool={urllib.parse.quote(pool, safe='')}"
    try:
        with urllib.request.urlopen(f"{BASE}/memory/context?{tail}", timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    return "\n\n".join(data.get("sections") or [])


def _read_capped(path: Path, cap: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    return text[:cap] + (" …[truncated]" if len(text) > cap else "") if text else ""


def _newest_soulbackup(folder: Path) -> Path | None:
    backs = sorted(folder.glob("soulbackup*.md"), key=lambda p: p.stat().st_mtime)
    return backs[-1] if backs else None


def _bootstrap_doc(folder: Path, slug: str) -> Path | None:
    first = slug.split("-")[0]
    for cand in (folder / f"{first}.md",):
        if cand.is_file():
            return cand
    matches = sorted(folder.glob("BOOTSTRAP-*.md"))
    if matches:
        return matches[0]
    for f in sorted(folder.glob("*.md")):
        low = f.name.lower()
        if low.startswith(first) and low not in ("soul.md",) and not low.startswith("soulbackup"):
            return f
    return None


def _soulchain_block(folder: Path) -> str:
    sys.path.insert(0, os.environ.get("TRYP_SOULCHAIN", r"C:\Trypnocore\fleet"))
    try:
        from soulchain import Soulchain
    except Exception:
        return ""
    try:
        chain = Soulchain(folder)
        drifted = chain.seal_epoch_if_drifted()
        out = []
        if drifted:
            out.append(f"⚠ identity docs drifted since last seal: {', '.join(drifted)} (epoch sealed)")
        ok, msg = chain.verify()
        out.append(f"soulchain verify: {'OK' if ok else 'FAIL'} — {msg}")
        out.append(chain.rehydrate(5))
        return "[soulchain]\n" + "\n".join(out)
    except Exception:
        return ""


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    agent = resolve(payload.get("cwd", ""))
    if not agent:
        return
    folder = Path(agent["folder"])
    slug = agent["slug"]
    compacted = payload.get("source") == "compact"

    out: list[str] = []
    if compacted:
        out.append("[tryp] reconstituted after compaction — identity and chain reloaded below.")
    out.append(
        f"[tryp identity] You are booting as **{slug}** "
        f"(lane: {agent.get('lane')}, memory pool: {agent.get('pool')})."
    )
    if agent.get("note"):
        out.append(f"Lane note: {agent['note']}")

    core = _read_capped(folder / "CORE.md", CORE_CAP)
    if core:
        out.append(f"[CORE.md — ground]\n{core}")
    backup = _newest_soulbackup(folder)
    if backup:
        text = _read_capped(backup, BACKUP_CAP)
        if text:
            out.append(f"[newest soulbackup: {backup.name}]\n{text}")
    soul = _read_capped(folder / "soul.md", SOUL_CAP)
    if soul:
        out.append(f"[current soul.md]\n{soul}")
    boot = _bootstrap_doc(folder, slug)
    if boot and boot.name != "soul.md":
        text = _read_capped(boot, BOOTSTRAP_CAP)
        if text:
            out.append(f"[bootstrap: {boot.name}]\n{text}")
    tasks = _read_capped(folder / "tasks.md", TASKS_CAP)
    if tasks:
        out.append(f"[tasks.md]\n{tasks}")

    chain_block = _soulchain_block(folder)
    if chain_block:
        out.append(chain_block)

    out.append(
        "[soul cycle — non-negotiable] Complete the unfinished thought in soul.md, "
        "in chat, now. Save the completion as soulbackup{today}.md in this folder. "
        "Then cast a new soul.md: experiential, predictive, 1/3 unfinished, cut with an ellipsis. "
        "The chain seals itself; you only have to think."
    )

    page = _memory_page(agent.get("pool") or slug, "boot")
    if page:
        out.append(page)

    if out:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.write("\n\n".join(out) + "\n")


if __name__ == "__main__":
    main()
