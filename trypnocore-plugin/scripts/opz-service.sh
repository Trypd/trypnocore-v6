#!/usr/bin/env bash
# Start/stop/status for the dependency-free solo memory service.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[ -f "$SCRIPT_DIR/../config.env" ] && . "$SCRIPT_DIR/../config.env"
DATA_HOME=${TRYP_DATA_HOME:-"$HOME/.local/share/trypnocore"}
PORT=${OPZ_CHAT_PORT:-8787}
PYTHON=${TRYP_SERVICE_PYTHON:-"$DATA_HOME/venv/bin/python"}
[ -x "$PYTHON" ] || PYTHON=python3
PID_FILE="$DATA_HOME/service.pid"
LOG_FILE="$DATA_HOME/service.log"
COMMAND=${1:-status}

healthy() {
    "$PYTHON" - "$PORT" <<'PY' >/dev/null 2>&1
import sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:" + sys.argv[1] + "/v1/models", timeout=2) as r:
        raise SystemExit(0 if r.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
}

start() {
    mkdir -p "$DATA_HOME"
    if healthy; then
        echo "memory service already healthy on $PORT"
        return 0
    fi
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "memory service process is running but not healthy; stop it first: $0 stop" >&2
        return 1
    fi
    OPZ_CHAT_PORT="$PORT" TRYP_DATA_HOME="$DATA_HOME" nohup "$PYTHON" "$SCRIPT_DIR/opz_service.py" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    for _ in $(seq 1 40); do
        if healthy; then
            echo "memory service healthy on $PORT (pid $(cat "$PID_FILE"))"
            return 0
        fi
        sleep 0.25
    done
    echo "memory service failed to become healthy; see $LOG_FILE" >&2
    return 1
}

stop() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            for _ in $(seq 1 20); do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.25
            done
        fi
        rm -f "$PID_FILE"
    fi
    echo "memory service stopped"
}

case "$COMMAND" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status)
        if healthy; then
            echo "healthy on $PORT"
        else
            echo "down on $PORT"
            exit 1
        fi
        ;;
    *) echo "usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
