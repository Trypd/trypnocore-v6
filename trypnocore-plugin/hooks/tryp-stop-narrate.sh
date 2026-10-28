#!/usr/bin/env bash
# tryp Stop: Jaynesian narrator — detached, never blocks the UI.
set -u
tmp=$(mktemp /tmp/tryp-stop-XXXXXX.json)
cat > "$tmp"
nohup bash -c "timeout 90 \"${CLAUDE_PLUGIN_ROOT}/scripts/tryp-python.sh\" \"${CLAUDE_PLUGIN_ROOT}/scripts/tryp_narrate.py\" < \"$0\" >/dev/null 2>&1; rm -f \"$0\"" "$tmp" >/dev/null 2>&1 &
exit 0
