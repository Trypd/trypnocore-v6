#!/usr/bin/env bash
# Trypnocore plugin installer — CC-WSL
# Installs the plugin and its local marketplace. Pass --retire-shims only after
# verifying the installed plugin to remove the legacy hooks and MCP entry.
# Idempotent: safe to re-run. Backs up settings.json + .claude.json first.
set -euo pipefail

RETIRE_SHIMS=0
if [ "${1:-}" = "--retire-shims" ]; then
    RETIRE_SHIMS=1
    shift
fi
PLUGIN_SRC="${1:-/mnt/c/Trypnocore/Trypnocore_V6/trypnocore-plugin}"
PLUGIN_DST="$HOME/.claude/plugins/trypnocore"
SETTINGS="$HOME/.claude/settings.json"
CLAUDE_JSON="$HOME/.claude.json"
STAMP=$(date +%Y%m%d-%H%M%S)

python3 - "$PLUGIN_SRC" <<'PYEOF'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "hooks/hooks.json"):
    with (root / rel).open(encoding="utf-8") as fh:
        json.load(fh)
for skill in ("your-turn", "planning-with-files", "metacognition"):
    if not (root / "skills" / skill / "SKILL.md").is_file():
        raise SystemExit(f"missing skills/{skill}/SKILL.md")
PYEOF

echo "==> backing up settings"
[ -f "$SETTINGS" ] && cp "$SETTINGS" "$SETTINGS.bak-tryp-plugin-$STAMP" || true
[ -f "$CLAUDE_JSON" ] && cp "$CLAUDE_JSON" "$CLAUDE_JSON.bak-tryp-plugin-$STAMP" || true

echo "==> installing plugin to $PLUGIN_DST"
mkdir -p "$PLUGIN_DST"
cp -r "$PLUGIN_SRC/." "$PLUGIN_DST/"
chmod +x "$PLUGIN_DST/hooks/"*.sh "$PLUGIN_DST/scripts/"*.sh

# Preserve the solo config when present; otherwise create the collective's
# Windows/WSL bridge configuration.
if [ ! -f "$PLUGIN_DST/config.env" ]; then
    cat >"$PLUGIN_DST/config.env" <<'EOF'
export TRYP_NATIVE=0
export TRYP_WINDOWS_PYTHON='C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe'
export TRYP_FLEET_REGISTRY='C:\Trypnocore\fleet\fleet-registry.json'
export TRYP_SOULCHAIN='C:\Trypnocore\fleet'
export OPZ_BASE_URL='http://127.0.0.1:8787'
export TRYP_COLLECTIVE=1
export OPZ_EMBED_MODEL=google/embeddinggemma-2
export OPZ_EMBED_DEVICE=cuda
EOF
fi

# Native /loop uses this prompt when invoked without an explicit prompt.
if [ ! -f "$HOME/.claude/loop.md" ]; then
    cp "$PLUGIN_DST/loop.md" "$HOME/.claude/loop.md"
fi

echo "==> registering local marketplace and plugin"
python3 - "$SETTINGS" "$PLUGIN_DST" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
d = json.loads(p.read_text()) if p.exists() else {}
d.setdefault("extraKnownMarketplaces", {})["local"] = {
    "source": {"source": "directory", "path": sys.argv[2]}
}
d.setdefault("enabledPlugins", {})["trypnocore@local"] = True
p.write_text(json.dumps(d, indent=2) + "\n")
print("local marketplace registered; trypnocore@local enabled")
PYEOF

# Persist the same local-marketplace/install records the Claude plugin CLI
# writes. This also makes headless installs deterministic.
python3 - "$HOME/.claude/plugins" "$PLUGIN_DST" "$STAMP" <<'PYEOF'
import json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
root, plugin, stamp = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def load(path, fallback):
    if path.exists():
        shutil.copy2(path, str(path) + f".bak-tryp-plugin-{stamp}")
        return json.loads(path.read_text())
    return fallback

known_path = root / "known_marketplaces.json"
known = load(known_path, {})
known["local"] = {
    "source": {"source": "directory", "path": plugin},
    "installLocation": plugin,
    "lastUpdated": now,
}
known_path.write_text(json.dumps(known, indent=2) + "\n")

installed_path = root / "installed_plugins.json"
installed = load(installed_path, {"version": 2, "plugins": {}})
version = json.loads((Path(plugin) / ".claude-plugin/plugin.json").read_text()).get("version", "unknown")
records = installed.setdefault("plugins", {}).setdefault("trypnocore@local", [])
previous = records[0].get("installedAt") if records else None
records[:] = [{
    "scope": "user",
    "installPath": plugin,
    "version": version,
    "installedAt": previous or now,
    "lastUpdated": now,
}]
installed_path.write_text(json.dumps(installed, indent=2) + "\n")
print("local marketplace and install records written")
PYEOF

if [ "${TRYP_NO_AGENT_SKILLS:-0}" != "1" ]; then
    echo "==> installing skills to every agent's .claude/skills/"
    for dir in /mnt/c/Trypnocore/Individuals/*/; do
        name=$(basename "$dir")
        [ "$name" = "Memory" ] && continue
        mkdir -p "$dir/.claude/skills"
        for skill in your-turn planning-with-files metacognition; do
            mkdir -p "$dir/.claude/skills/$skill"
            cp -r "$PLUGIN_DST/skills/$skill/." "$dir/.claude/skills/$skill/"
        done
    done
fi

if [ "$RETIRE_SHIMS" -eq 0 ]; then
    echo ""
    echo "Plugin installed; legacy hooks left untouched. Verify it, then rerun with --retire-shims."
    exit 0
fi

echo "==> retiring loose shims"
python3 - "$SETTINGS" "$CLAUDE_JSON" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
d = json.loads(p.read_text())
removed = 0
for event in ("SessionStart", "UserPromptSubmit", "Stop", "PreCompact"):
    hooks = d.get("hooks", {}).get(event, [])
    before = len(hooks)
    d["hooks"][event] = [
        group for group in hooks
        if not any(
            "tryp-" in json.dumps(h) or "opz-memory-inject" in json.dumps(h)
            for h in group.get("hooks", [])
        )
    ]
    removed += before - len(d["hooks"][event])
p.write_text(json.dumps(d, indent=2) + "\n")
print(f"retired {removed} loose hook registrations")

p = Path(sys.argv[2])
d = json.loads(p.read_text()) if p.exists() else {}
server = d.get("mcpServers", {}).get("opz-memory", {})
if "OmegaPrimeZero" in json.dumps(server) and "opz_memory.py" in json.dumps(server):
    del d["mcpServers"]["opz-memory"]
    p.write_text(json.dumps(d, indent=2) + "\n")
    print("retired global opz-memory registration; plugin now owns it")
else:
    print("global opz-memory registration left unchanged (not the legacy OPZ entry)")
PYEOF

rm -f "$HOME/.claude/hooks/tryp-session-start.sh" \
      "$HOME/.claude/hooks/tryp-prompt-context.sh" \
      "$HOME/.claude/hooks/tryp-stop-seal.sh" \
      "$HOME/.claude/hooks/tryp-stop-narrate.sh" \
      "$HOME/.claude/hooks/tryp-precompact-distill.sh" \
      "$HOME/.claude/hooks/opz-memory-inject.sh"
echo "loose shim files deleted (plugin now owns them)"

echo ""
echo "Trypnocore plugin installed. Restart running CC sessions or use /reload-plugins."
echo "  Plugin:  $PLUGIN_DST"
echo "  Hooks:   plugin-relative, owned by trypnocore@local"
echo "  Skills:  your-turn, planning-with-files, metacognition"
echo "  MCP:     plugin:trypnocore:opz-memory"
