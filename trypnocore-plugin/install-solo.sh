#!/usr/bin/env bash
# Standalone Linux/WSL installer: native memory service + Claude plugin.
set -euo pipefail
PLUGIN_SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DATA_HOME=${TRYP_DATA_HOME:-"$HOME/.local/share/trypnocore"}
PLUGIN_DST="$HOME/.claude/plugins/trypnocore"
PORT=${OPZ_CHAT_PORT:-8787}

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required" >&2
    exit 1
fi

echo "==> creating isolated Python environment in $DATA_HOME/venv"
mkdir -p "$DATA_HOME"
python3 -m venv "$DATA_HOME/venv"
"$DATA_HOME/venv/bin/python" -m pip install --disable-pip-version-check 'mcp>=1.26,<2'

mkdir -p "$PLUGIN_DST"
cat >"$PLUGIN_DST/config.env" <<EOF
export TRYP_NATIVE=1
export TRYP_DATA_HOME=$(printf '%q' "$DATA_HOME")
export TRYP_PYTHON=$(printf '%q' "$DATA_HOME/venv/bin/python")
export TRYP_SERVICE_PYTHON=$(printf '%q' "$DATA_HOME/venv/bin/python")
export TRYP_COLLECTIVE=0
export OPZ_CHAT_PORT=$(printf '%q' "$PORT")
export OPZ_BASE_URL=$(printf '%q' "http://127.0.0.1:$PORT")
export OPZ_EMBED_MODEL=
export OPZ_EMBED_DEVICE=cpu
EOF

echo "==> installing plugin"
TRYP_NATIVE=1 TRYP_DATA_HOME="$DATA_HOME" TRYP_NO_AGENT_SKILLS=1 "$PLUGIN_SRC/install.sh" "$PLUGIN_SRC"

echo "==> starting native memory service"
"$PLUGIN_DST/scripts/opz-service.sh" restart

cat <<EOF

Solo installation complete.
  Plugin: $PLUGIN_DST
  Memory: http://127.0.0.1:$PORT
  Config: $PLUGIN_DST/config.env
  Service: $PLUGIN_DST/scripts/opz-service.sh {start|stop|restart|status}

Restart Claude Code or run /reload-plugins. Other agents can use the same MCP
command or the loopback HTTP memory endpoints documented in README.md.
EOF
