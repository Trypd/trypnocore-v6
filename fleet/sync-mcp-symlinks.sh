#!/usr/bin/env bash
# Trypnocore v6 — Synchronize Canonical MCP Config via Symlinks
# Replaces per-agent .mcp.json files with a symlink to fleet/mcp.canonical.json.
set -euo pipefail

REG="/mnt/c/Trypnocore/fleet/fleet-registry.json"
CANONICAL="/mnt/c/Trypnocore/fleet/mcp.canonical.json"

if [ ! -f "$REG" ]; then
    echo "[ERROR] Registry not found at $REG"
    exit 1
fi

if [ ! -f "$CANONICAL" ]; then
    echo "[ERROR] Canonical config not found at $CANONICAL"
    exit 1
fi

python3 - "$REG" "$CANONICAL" <<'PYEOF'
import json, os, sys

reg_path = sys.argv[1]
canonical_path = sys.argv[2]

with open(reg_path, "r", encoding="utf-8") as f:
    reg = json.load(f)

count = 0
for agent in reg.get("agents", []):
    raw_folder = agent.get("folder", "")
    folder = raw_folder.replace("\\", "/").replace("C:", "/mnt/c")
    if not os.path.isdir(folder):
        print(f"[SKIP] Directory not found: {folder}")
        continue
    
    target = os.path.join(folder, ".mcp.json")
    
    # If regular file exists, backup once
    if os.path.exists(target) and not os.path.islink(target):
        bak = target + ".bak-prev6"
        if not os.path.exists(bak):
            os.rename(target, bak)
            print(f"[BACKUP] {target} -> .bak-prev6")
        else:
            os.remove(target)
    elif os.path.islink(target):
        os.unlink(target)
        
    try:
        os.symlink(canonical_path, target)
        print(f"[SYMLINK] {target} -> {canonical_path}")
        count += 1
    except Exception as e:
        print(f"[ERROR] Could not symlink {target}: {e}")

print(f"\nSuccessfully linked {count} agent workspaces to canonical MCP config.")
PYEOF
