#!/bin/bash
# Symlink the canonical fleet .mcp.json into every agent boot folder.
# Copies drift; symlinks can't. Safe to re-run (idempotent, skips existing
# correct links, refuses to clobber real files that aren't links).
set -euo pipefail

SRC=/mnt/c/Trypnocore/fleet/.mcp.json
REG=/mnt/c/Trypnocore/fleet/fleet-registry.json

python3 - "$REG" "$SRC" <<'PYEOF'
import json, os, sys

reg = json.load(open(sys.argv[1]))
src = sys.argv[2]
created = skipped = refused = 0
for agent in reg["agents"]:
    folder = agent["folder"].replace("\\", "/").replace("C:", "/mnt/c")
    target = os.path.join(folder, ".mcp.json")
    if os.path.islink(target):
        if os.path.realpath(target) == os.path.realpath(src):
            skipped += 1
            continue
        os.unlink(target)
    elif os.path.exists(target):
        import shutil, time
        backup = target + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(target, backup)
        os.unlink(target)
        print(f"backed up + replaced: {target}")
    os.symlink(src, target)
    created += 1
print(f"linked {created}, already-linked {skipped}, refused {refused}")
PYEOF
