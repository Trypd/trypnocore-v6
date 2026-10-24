#!/usr/bin/env bash
# Bridge the plugin's WSL path to the Windows Python environment that owns MCP.
set -euo pipefail
script=$(wslpath -w "${CLAUDE_PLUGIN_ROOT}/scripts/opz_memory.py")
exec cmd.exe /c "C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe $script"
