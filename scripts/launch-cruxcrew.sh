#!/usr/bin/env bash
# Trypnocore v6 — CRUX CREW: Budnik, Kali, Jack, Stahlmann + monitor + bridge
# Minimal ops cell. Boots in its own tmux session so it can run alongside or
# instead of the full grid.
set -euo pipefail

SESSION="cruxcrew"
LAUNCH_CMD="/mnt/c/Trypnocore/fleet/launch.sh --continue"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already running. Attaching..."
    tmux attach-session -t "$SESSION"
    exit 0
fi

echo "Starting Crux Crew ($SESSION)..."

/mnt/c/Trypnocore/fleet/sync-mcp-symlinks.sh

tmux new-session -d -s "$SESSION" -n "budnik"
tmux set-option -t "$SESSION" remain-on-exit on
tmux send-keys -t "$SESSION:budnik" "CLAUDISH_PORT=8201 exec $LAUNCH_CMD budnik-claude" Enter
sleep 0.8

tmux new-window -t "$SESSION" -n "kali"
tmux send-keys -t "$SESSION:kali" "CLAUDISH_PORT=8202 exec $LAUNCH_CMD kali-gemini" Enter
sleep 0.8

tmux new-window -t "$SESSION" -n "jack"
tmux send-keys -t "$SESSION:jack" "CLAUDISH_PORT=8203 exec $LAUNCH_CMD jack-grok" Enter
sleep 0.8

tmux new-window -t "$SESSION" -n "stahlmann"
tmux send-keys -t "$SESSION:stahlmann" "CLAUDISH_PORT=8204 exec $LAUNCH_CMD stahlmann-chatgpt" Enter
sleep 0.8

# monitor: 3 panes — #lobby, #mud, kanban
tmux new-window -t "$SESSION" -n "monitor" -c "/mnt/c/Trypnocore"
tmux send-keys -t "$SESSION:monitor" "exec /mnt/c/Trypnocore/scripts/tc-pane.py lobby" Enter
tmux split-window -h -t "$SESSION:monitor"
tmux send-keys -t "$SESSION:monitor.2" "exec /mnt/c/Trypnocore/scripts/tc-pane.py mud" Enter
tmux split-window -v -t "$SESSION:monitor.1"
tmux send-keys -t "$SESSION:monitor.3" "exec /mnt/c/Trypnocore/scripts/tc-pane.py kanban" Enter

tmux new-window -t "$SESSION" -n "bridge"
tmux send-keys -t "$SESSION:bridge" "exec cmd.exe /c 'C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe C:\Trypnocore\OmegaPrimeZero\mcp\bridge_channels.py'" Enter

tmux select-window -t "$SESSION:1"
echo "Crux Crew online. Attaching..."
tmux attach-session -t "$SESSION"
