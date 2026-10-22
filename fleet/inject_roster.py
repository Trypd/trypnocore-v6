"""Inject the current fleet roster into every agent's memory pool."""
import json
import urllib.request
from pathlib import Path

REG = json.loads(Path(r"C:\Trypnocore\fleet\fleet-registry.json").read_text(encoding="utf-8"))
BASE = "http://127.0.0.1:8787"

roster = []
pending = []
for a in REG["agents"]:
    if a["lane"] == "TBD":
        if a["slug"] != "memory":
            pending.append(a["slug"])
        continue
    entry = f"{a['slug']}: {a['lane']}"
    if a.get("note"):
        entry += f" ({a['note']})"
    roster.append(entry)
roster_text = (
    "Trypnocore fleet roster (2026-10-07, from fleet-registry.json): "
    + "; ".join(roster)
    + ". Blitzø Buckzo = blitz-kimi on kc@k3 (Kimi K3), surgery mode cyberkimi. "
    + "Dr. Elara Vance = vance-qwen on qwenmaas@qwen3.8-max — she/her, dyad with Mr. Ronan Hart. "
    + "Each agent boots in CC-WSL via fleet/launch.sh <slug>, memory pool = slug, identity hash over bootstrap docs."
)
if pending:
    roster_text += " Members awaiting lanes (in the collective, not yet bootable): " + ", ".join(pending) + "."

ok = 0
for a in REG["agents"]:
    slug = a["slug"]
    if slug == "memory":
        continue
    body = json.dumps({
        "line": f"remember that the fleet roster is: {roster_text}",
        "pool": slug,
    }).encode()
    req = urllib.request.Request(BASE + "/memory/remember", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
        if resp.get("remembered"):
            ok += 1
    except Exception as exc:
        print(f"FAIL {slug}: {exc}")

print(f"roster injected into {ok} pools")
