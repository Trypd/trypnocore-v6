#!/usr/bin/env bash
# Select native solo Python or the collective's Windows/WSL Python bridge.
set -euo pipefail
[ -f "${CLAUDE_PLUGIN_ROOT}/config.env" ] && . "${CLAUDE_PLUGIN_ROOT}/config.env"
if [ "${TRYP_NATIVE:-0}" = "1" ]; then
    root=${TRYP_DATA_HOME:-"$HOME/.local/share/trypnocore"}
    python=${TRYP_PYTHON:-"$root/venv/bin/python"}
    [ -x "$python" ] || python=python3
    exec "$python" "$@"
fi
script=$1
shift
python=${TRYP_WINDOWS_PYTHON:-'C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe'}
script_win=$(wslpath -w "$script")
exec cmd.exe /c "$python $script_win $*"
