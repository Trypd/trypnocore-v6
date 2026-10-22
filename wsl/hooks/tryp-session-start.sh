#!/usr/bin/env bash
# tryp SessionStart: personality loader — boot block, soul.md, semantic memory page.
# Fails silent; a boot must never error.
set -u
input=$(cat)
cwd=$(printf "%s" "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get(\"cwd\",\"\"), end=\"\")" 2>/dev/null)
[ -z "$cwd" ] && exit 0
printf "%s" "$input" | TRYPD_CWD="$cwd" WSLENV="TRYPD_CWD" timeout 15 cmd.exe /c "C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe C:\Trypnocore\OmegaPrimeZero\mcp\tryp_session_boot.py" 2>/dev/null
exit 0
