#!/usr/bin/env bash
# tryp Stop: Jaynesian narrator — detached, never blocks the UI.
set -u
tmp=$(mktemp /tmp/tryp-stop-XXXXXX.json)
cat > "$tmp"
nohup bash -c "timeout 90 cmd.exe /c \"C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe C:\Trypnocore\OmegaPrimeZero\mcp\tryp_narrate.py\" < \"$0\" >/dev/null 2>&1; rm -f \"$0\"" "$tmp" >/dev/null 2>&1 &
exit 0
