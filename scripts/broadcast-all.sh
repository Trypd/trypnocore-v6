#!/usr/bin/env bash
# ==============================================================================
# TRYPNOCORE v6 — FLEET BROADCAST / AUTO-POKE SCRIPT
# Sends a command/prompt to every active agent pane in the tmux session.
# Safely skips non-agent utility windows (e.g. monitor, hub).
#
# Usage:
#   ./scripts/broadcast-all.sh ["message"] [session_name] [delay_seconds] [--dry-run]
# ==============================================================================

set -uo pipefail

MESSAGE="${1:-okay, boot}"
SESSION="${2:-trypnocore}"
DELAY="${3:-0}"
DRY_RUN=false

for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=true
    fi
done

if [[ "$MESSAGE" == "--dry-run" ]]; then
    MESSAGE="okay, boot"
fi

if [ "$DELAY" -gt 0 ]; then
    sleep "$DELAY"
fi

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[broadcast] Session '$SESSION' not found. Exiting."
    exit 0
fi

echo "[broadcast] Targeting agent panes in session '$SESSION'..."

poke_pane() {
    local p_id="$1"
    local w_name="$2"
    local msg="$3"
    local is_dry="$4"

    local ready=0
    for i in {1..60}; do
        local buf
        buf=$(tmux capture-pane -p -t "$p_id" 2>/dev/null || true)
        # If pane entered Claude Code's scroll pager (e.g. SCROLL 10/10 · q live), send 'q' to return to live prompt
        if echo "$buf" | grep -q "SCROLL "; then
            tmux send-keys -t "$p_id" "q"
            sleep 0.3
            buf=$(tmux capture-pane -p -t "$p_id" 2>/dev/null || true)
        fi

        if echo "$buf" | grep -q 'bypass permissions'; then
            ready=1
            break
        fi
        sleep 1
    done

    if [ "$ready" -eq 1 ]; then
        if [ "$is_dry" = "true" ]; then
            echo "[broadcast:dry-run] Ready: $w_name ($p_id) -> would send: '$msg'"
        else
            sleep 0.5
            tmux send-keys -t "$p_id" C-u "$msg" Enter
            echo "[broadcast] Poked $w_name ($p_id)"
        fi
    else
        if [ "$is_dry" = "true" ]; then
            echo "[broadcast:dry-run] Warning: $w_name ($p_id) timed out waiting for prompt"
        else
            tmux send-keys -t "$p_id" C-u "$msg" Enter
            echo "[broadcast] Warning: $w_name ($p_id) timed out waiting for prompt, sent anyway"
        fi
    fi
}

pids=()
for entry in $(tmux list-panes -s -t "$SESSION" -F '#{pane_id}:#{window_name}'); do
    pane_id="${entry%%:*}"
    win_name="${entry##*:}"

    # Skip utility/feed windows
    if [[ "$win_name" == "monitor" || "$win_name" == "hub" ]]; then
        continue
    fi

    poke_pane "$pane_id" "$win_name" "$MESSAGE" "$DRY_RUN" &
    pids+=($!)
done

for p in "${pids[@]}"; do
    wait "$p" 2>/dev/null || true
done

echo "[broadcast] Broadcast to all agent panes finished."
