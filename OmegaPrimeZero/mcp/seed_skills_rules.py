"""Seed the community skills + rules pools.

Rules: parsed from the collective cerebrum (C:/Trypnocore/.wolf/cerebrum.md),
one atom per bullet, tier ([PERMANENT]/SLOW/FAST) preserved in the claim text.

Skills: one atom per SKILL.md under C:/Trypnocore/.agents/skills/ — name,
description, and the on-disk path. The atom is a pointer card; the agent reads
the full file only when the card matches, which is what "lazy loaded" means.

Run with the OPZ server UP:  python mcp/seed_skills_rules.py
Pointer-deduped; safe to re-run after editing cerebrum.md or adding skills.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8787"
CEREBRUM = Path(r"C:\Trypnocore\.wolf\cerebrum.md")
SKILLS_ROOT = Path(r"C:\Trypnocore\.agents\skills")
MAX_RULE_CHARS = 600


def _remember(pool: str, line: str) -> bool:
    body = json.dumps({"line": line, "pool": pool}).encode()
    req = urllib.request.Request(
        f"{BASE}/memory/remember", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read()).get("remembered", 0) > 0
    except Exception:
        return False


def cerebrum_rules() -> list[str]:
    text = CEREBRUM.read_text(encoding="utf-8", errors="replace")
    rules: list[str] = []
    section = ""
    for raw in text.splitlines():
        header = re.match(r"^##\s+(.*)", raw)
        if header:
            section = header.group(1).strip()
            continue
        m = re.match(r"^-\s+\*\*(.+?)\*\*\s*(?:\(([^)]*)\))?\s*—\s*(.*)", raw, re.DOTALL)
        if not m:
            continue
        title, datestr, body = m.group(1), m.group(2) or "", m.group(3)
        tier = "PERMANENT" if "PERMANENT" in (section + title).upper() else (
            "SLOW" if "SLOW" in title.upper() else "FAST"
        )
        claim = f"rule [{tier}] {title}"
        if datestr:
            claim += f" ({datestr})"
        claim += f": {body.strip()}"
        rules.append(claim[:MAX_RULE_CHARS])
    return rules


def skill_cards() -> list[str]:
    cards: list[str] = []
    for skill_md in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        name = skill_md.parent.name
        desc = ""
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if fm:
            dm = re.search(r"description:\s*(.+?)(?:\n[a-z_]+:|$)", fm.group(1), re.DOTALL)
            if dm:
                desc = " ".join(dm.group(1).split())
        if not desc:
            first = next((l for l in text.splitlines() if l.strip() and not l.startswith(("#", "---"))), "")
            desc = first.strip()
        cards.append(
            f"skill: {name} — {desc[:360]} "
            f"[full definition: {skill_md.as_posix()} — read it before using]"
        )
    return cards


def main() -> None:
    rules = cerebrum_rules()
    skills = skill_cards()
    print(f"cerebrum rules parsed: {len(rules)}; skill cards: {len(skills)}")
    r_ok = sum(1 for r in rules if _remember("rules", f"remember that {r}"))
    s_ok = sum(1 for s in skills if _remember("skills", f"remember that {s}"))
    print(f"rules pool +{r_ok}, skills pool +{s_ok}")


if __name__ == "__main__":
    main()
