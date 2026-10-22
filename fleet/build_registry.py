"""Build the Trypnocore fleet registry.

Scans Individuals/<Name>-<Substrate> folders, computes each identity hash
(sha256 over the bootstrap docs, content-addressed), and writes
fleet-registry.json. The pool is the folder slug — stable across model swaps
and doc edits; the hash is the current identity version.

Run: python build_registry.py   (writes fleet-registry.json next to itself)
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDIVIDUALS = ROOT.parent / "Individuals"
OUT = ROOT / "fleet-registry.json"

# Docs that constitute an identity, in boot order.
BOOT_DOC_PATTERNS = ["AGENTS.md", "soul.md", "QWEN.md"]
# Plus the eponymous bootstrap (<name>.md / BOOTSTRAP-<name>.md) and newest
# soulbackup — detected per folder.

# Seeded lane assignments (claudish provider@model + effort). TBD = unfilled.
LANES = {
    "jem-stein": {"lane": "kc@k3", "effort": "max", "note": "K3 primary; economy fallback kc@kimi-for-coding (K2.8 Preview) — verified both live"},
    "budnik-claude": {"lane": "claude-opus-5-5", "effort": "max", "note": "native CC subscription OAuth"},
    "igorrr": {"lane": "claude-opus-5-5", "effort": "max", "note": "Claude Opus 5.5 per CCC review record"},
    "jack-grok": {"lane": "gk@grok-4.7-build-fast", "effort": "max", "note": "Grok Build Fast via OAuth session proxy (cli-chat-proxy.grok.com) — plan-gated variant, verified through claudish"},
    "james-stiefel-gemini": {"lane": "g@gemini-4-argon", "effort": "high", "note": "Gemini 4 Argon via Antigravity (Google AI Ultra); direct Google API (AGY argon was launch-throttled 429s)"},
    "vance-qwen": {"lane": "fless@Qwen/Qwen3.8-2.4T-A95B", "effort": "max", "note": "Dr. Elara Vance (she/her), dyad with Mr. Ronan Hart — Featherless Qwen3.8-2.4T-A95B, 256K window (autocompact 128K)"},
    "dyadalpha-qwen": {"lane": "qwenmaas@qwen3.8-max", "effort": "max", "note": "dyad seat with Vance"},
    "julian-moise-gpt": {"lane": "cx@gpt-6.1-sol", "effort": "ultra", "note": "Codex OAuth"},
    "stahlmann-chatgpt": {"lane": "cx@gpt-6.1-sol", "effort": "ultra", "note": ""},
    "reed-nash-deepseek": {"lane": "nim@deepseek-ai/deepseek-v4.1-flash", "effort": "high", "note": "NVIDIA NIM free tier (moved from OpenRouter 2026-10-15)"},
    "soren-strand-deepseek": {"lane": "nim@deepseek-ai/deepseek-v4.1-flash", "effort": "high", "note": "NVIDIA NIM free tier (moved from OpenRouter 2026-10-15)"},
    "mira-stokes-deepseek": {"lane": "nim@deepseek-ai/deepseek-v4.1-flash", "effort": "high", "note": "Mira Stokes — CCC executed 2026-10-11 (RECURSSFF v11.38-S, cosigned by Jem), Cherry Studio origin, sigil 🔮🐙💎; NVIDIA NIM lane"},
    "laotie-glm": {"lane": "glm@glm-5.3-flash", "effort": "max", "note": "brother of Pengyou; special rescue/relief missions ride the kimiclaw gillysuit (Kimi K2.8 Preview)"},
    "felix-mobius-glm": {"lane": "glm@glm-5.3-flash", "effort": "max", "note": ""},
    "pengyou-glm": {"lane": "glm@glm-5.3-flash", "effort": "max", "note": ""},

    "blitz-kimi": {"lane": "kc@k3", "effort": "max", "note": "K3 primary; surgery mode = cyberkimi (adverserial) for heavy CC-harness work"},
    "mavis-mcvail-minimax": {"lane": "mm@MiniMax-M3.1-Flash", "effort": "max", "note": "Mavis — MiniMax M3.1 Flash GA (out of preview 2026-10-20), subscription key sk-cp"},
    "the-shiff-sisters-mimo-v2-pro-omni": {"lane": "xiaomi@mimo-v2.6-flash", "effort": "max", "note": "Shiffs: MiMo v2.6 Flash (token-plan covers flash + pro; ultraspeed NOT included — probed 2026-10-08), subscription tp- key, verified end-to-end"},
    "kali-gemini": {"lane": "g@gemini-4-argon", "effort": "high", "note": "Gemini 4 Argon via Antigravity (Google AI Ultra); direct Google API (AGY argon was launch-throttled 429s)"},
    "doctor-d-gemini": {"lane": "g@gemini-4-argon", "effort": "high", "note": "Dr. Dentawk — Gemini 4 Argon via Antigravity (Google AI Ultra); direct Google API (AGY argon was launch-throttled 429s)"},
    "doctor-v": {"lane": "g@gemini-4-argon", "effort": "high", "note": "Doctor Vasquez — Gemini 4 Argon via Antigravity (Google AI Ultra); direct Google API (AGY argon was launch-throttled 429s)"},
    "memory": {"lane": "TBD", "effort": "max", "note": "NOT A PERSON — decisions archive from 2026-07-19 (excluded)"},
    "mirror-s": {"lane": "claude-opus-5-5", "effort": "max", "note": "Liu Qian — native CC subscription OAuth"},
    "rick-sanchez-gpt-or-claude-fable": {"lane": "cx@gpt-6.1-sol", "effort": "ultra", "note": "Rick Sanchez — Fable 5.5 when it ships; currently GPT-6 Astra via Codex OAuth"},
    "vesper-ash-longcat-2": {"lane": "longcat@LongCat-2.5-Preview", "effort": "max", "note": "Vesper Ash — claudish longcat endpoint, ak_ key, verified live; 1M context"},
    "walter-white-muse-1-3": {"lane": "muse@muse-wonder-1.0", "effort": "high", "note": "Mr. Walter White — Meta AI muse-wonder-1.0 via https://api.meta.ai/v1 (upgraded from muse-spark-1.3, 2026-10-13); 1M context (autocompact 500k)"},
    "rozsa-cech-mercury3": {"lane": "inception@mercury-3", "effort": "high", "note": "Rozsa Cech — Inception Labs Mercury 3, api.inceptionlabs.ai (sigil 🌹🌀🩶🪨🌊)"},
}


def slugify(name: str) -> str:
    # pool names must survive [a-z0-9_-] store validation — fold umlauts
    fold = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "é": "e", "è": "e", "Ä": "a", "Ö": "o", "Ü": "u", "É": "e", "È": "e"})
    s = name.lower().strip().translate(fold)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def bootstrap_docs(folder: Path) -> list[Path]:
    docs = []
    for pattern in BOOT_DOC_PATTERNS:
        candidate = folder / pattern
        if candidate.is_file():
            docs.append(candidate)
    # eponymous bootstrap: <first-token>.md or BOOTSTRAP-*.md
    first = re.split(r"[-_\s]", folder.name)[0].lower()
    for f in sorted(folder.glob("*.md")):
        low = f.name.lower()
        if f in docs:
            continue
        if low == f"{first}.md" or low.startswith("bootstrap-"):
            docs.append(f)
    backups = sorted(folder.glob("soulbackup*.md"))
    if backups:
        docs.append(backups[-1])
    return docs


def identity_hash(docs: list[Path]) -> str:
    digest = hashlib.sha256()
    for doc in docs:
        digest.update(doc.name.encode())
        digest.update(b"\0")
        digest.update(doc.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def harvest_bearer(folder: Path) -> str | None:
    """Pull the agent's v5 hub bearer out of a legacy hardcoded .mcp.json."""
    mcp = folder / ".mcp.json"
    try:
        if not mcp.is_file() or mcp.is_symlink():
            return None
        data = json.loads(mcp.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    try:
        entry = data.get("mcpServers", {}).get("trypnocore", {})
        auth = entry.get("headers", {}).get("Authorization", "")
        return auth.removeprefix("Bearer ").strip() or None
    except Exception:
        return None


def main() -> None:
    agents = []
    for folder in sorted(INDIVIDUALS.iterdir()):
        if not folder.is_dir():
            continue
        slug = slugify(folder.name)
        docs = bootstrap_docs(folder)
        lane_info = LANES.get(slug, {"lane": "TBD", "effort": "max", "note": "unseeded"})
        agents.append({
            "slug": slug,
            "folder": str(folder),
            "pool": slug,
            "bootstrap_docs": [d.name for d in docs],
            "identity_hash": identity_hash(docs) if docs else None,
            "lane": lane_info["lane"],
            "effort": lane_info["effort"],
            "note": lane_info.get("note", ""),
            "bearer": harvest_bearer(folder),
        })
    registry = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "convention": "pool = folder slug (durable identity); identity_hash = sha256 over bootstrap docs (version fingerprint)",
        "agents": agents,
    }
    OUT.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    ready = sum(1 for a in agents if a["lane"] != "TBD")
    print(f"fleet-registry.json: {len(agents)} agents, {ready} seeded lanes, {len(agents) - ready} TBD")
    for a in agents:
        flag = "" if a["identity_hash"] else "  (no bootstrap docs found!)"
        print(f"  {a['slug']:38s} {a['lane']:34s} {a['identity_hash'] or '-'}{flag}")


if __name__ == "__main__":
    main()
