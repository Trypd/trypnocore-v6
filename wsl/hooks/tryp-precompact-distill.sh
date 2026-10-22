#!/usr/bin/env bash
# tryp PreCompact: distill the outgoing transcript into pool atoms before it vanishes.
# Detached — compaction must never wait on the model call.
set -u
tmp=$(mktemp /tmp/tryp-precompact-XXXXXX.json)
cat > "$tmp"
nohup bash -c "timeout 180 cmd.exe /c \"C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe C:\Trypnocore\OmegaPrimeZero\mcp\tryp_distill.py\" < \"$0\" >/dev/null 2>&1; rm -f \"$0\"" "$tmp" >/dev/null 2>&1 &
exit 0
