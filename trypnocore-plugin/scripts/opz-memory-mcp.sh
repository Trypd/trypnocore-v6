#!/usr/bin/env bash
# Bridge the plugin's WSL path to the Windows Python environment that owns MCP.
set -euo pipefail
exec "${CLAUDE_PLUGIN_ROOT}/scripts/tryp-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/opz_memory.py"
