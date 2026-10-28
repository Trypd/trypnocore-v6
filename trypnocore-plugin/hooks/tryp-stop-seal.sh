#!/usr/bin/env bash
# tryp Stop seal gate: seal a turn ring + epoch-drift check. Fast, synchronous.
set -u
input=$(cat)
cwd=$(printf "%s" "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get(\"cwd\",\"\"), end=\"\")" 2>/dev/null)
[ -z "$cwd" ] && exit 0
printf "%s" "$input" | TRYPD_CWD="$cwd" WSLENV="TRYPD_CWD" timeout 10 "${CLAUDE_PLUGIN_ROOT}/scripts/tryp-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/tryp_seal.py" 2>/dev/null
exit 0
