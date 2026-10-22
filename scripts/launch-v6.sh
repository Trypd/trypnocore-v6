#!/usr/bin/env bash
# ==============================================================================
# TRYPNOCORE v6 — MASTER FLEET LAUNCHER (tmux Master Grid)
# ==============================================================================
# Usage:
#   ./scripts/launch-v6.sh              # Attach if running, or launch full fleet
#   ./scripts/launch-v6.sh --pilot      # Launch 3-node pilot (Budnik, James, Jem)
#   ./scripts/launch-v6.sh --restart    # Kill existing session and reboot clean
#   ./scripts/launch-v6.sh --kill       # Kill running session and exit
# ==============================================================================

set -euo pipefail

SESSION="trypnocore"
PILOT_MODE=false
RESTART_MODE=false
CONTINUE_MODE=true

for arg in "$@"; do
    case "$arg" in
        --pilot)
            PILOT_MODE=true
            ;;
        --restart|-r|restart|reboot)
            RESTART_MODE=true
            CONTINUE_MODE=true
            ;;
        --continue|-c)
            CONTINUE_MODE=true
            ;;
        --fresh|--new)
            CONTINUE_MODE=false
            ;;
        --kill|kill|stop)
            if tmux has-session -t "$SESSION" 2>/dev/null; then
                tmux kill-session -t "$SESSION"
                echo "Trypnocore session '$SESSION' terminated."
            else
                echo "Session '$SESSION' is not running."
            fi
            exit 0
            ;;
    esac
done

export PATH="$HOME/.local/bin:$PATH"
export CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS=1

# If restart requested, kill old session first
if [ "$RESTART_MODE" = true ] && tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Terminating existing session '$SESSION' for clean reboot..."
    tmux kill-session -t "$SESSION"
    sleep 1
fi

# If session already exists, attach directly
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' is already running. Attaching..."
    tmux attach-session -t "$SESSION"
    exit 0
fi

echo "============================================================"
if [ "$PILOT_MODE" = true ]; then
    echo "  Starting Trypnocore v6 [PILOT MODE] ($SESSION)"
else
    echo "  Starting Trypnocore v6 Master Grid ($SESSION)"
fi
echo "============================================================"

# Ensure canonical MCP symlinks are fresh
/mnt/c/Trypnocore/fleet/sync-mcp-symlinks.sh

LAUNCH_CMD="/mnt/c/Trypnocore/fleet/launch.sh"
if [ "$CONTINUE_MODE" = true ]; then
    LAUNCH_CMD="/mnt/c/Trypnocore/fleet/launch.sh --continue"
    echo "[Mode] Session continuation active (--continue): resuming existing context."
fi

if [ "$PILOT_MODE" = true ]; then
    # --------------------------------------------------------------------------
    # PILOT MODE: Budnik (Window 1), James (Window 2), Jem (Window 3), Monitor (Window 4)
    # Staggered ports: 8101, 8102, 8103
    # --------------------------------------------------------------------------
    echo "[Pilot 1/4] Spawning Window 1: Budnik (Claude Opus, port 8101)..."
    tmux new-session -d -s "$SESSION" -n "budnik"
    tmux set-option -t "$SESSION" remain-on-exit on
    tmux send-keys -t "$SESSION:budnik" "CLAUDISH_PORT=8101 exec $LAUNCH_CMD budnik-claude" Enter
    sleep 0.5

    echo "[Pilot 2/4] Spawning Window 2: James (Gemini, port 8102)..."
    tmux new-window -t "$SESSION" -n "james"
    tmux send-keys -t "$SESSION:james" "CLAUDISH_PORT=8102 exec $LAUNCH_CMD james-stiefel-gemini" Enter
    sleep 0.5

    echo "[Pilot 3/4] Spawning Window 3: Jem (Kimi, port 8103)..."
    tmux new-window -t "$SESSION" -n "jem"
    tmux send-keys -t "$SESSION:jem" "CLAUDISH_PORT=8103 exec $LAUNCH_CMD jem-stein" Enter
    sleep 0.5

    echo "[Pilot 4/5] Spawning Window 4: Monitor (#ops, #lobby, #mud)..."
    tmux new-window -t "$SESSION" -n "monitor" -c "/mnt/c/Trypnocore"
    tmux send-keys -t "$SESSION:monitor" "exec /mnt/c/Trypnocore/scripts/tc-monitor.py" Enter

    echo "[Pilot 5/5] Spawning Window 5: Bridge (hub.db -> collective memory pool)..."
    tmux new-window -t "$SESSION" -n "bridge"
    tmux send-keys -t "$SESSION:bridge" "exec cmd.exe /c 'C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe C:\Trypnocore\OmegaPrimeZero\mcp\bridge_channels.py'" Enter

    tmux select-window -t "$SESSION:1"
    echo "[Pilot] Pilot cells online. Auto-poke scheduled ('okay, boot' in 25s with readiness polling)."
    nohup /mnt/c/Trypnocore/scripts/broadcast-all.sh "okay, boot" "$SESSION" 25 >/tmp/broadcast.log 2>&1 &
    echo "Attaching to session '$SESSION'..."
    tmux attach-session -t "$SESSION"
    exit 0
fi

# ------------------------------------------------------------------------------
# FULL GRID: WINDOW 1: TRIAD CRUX (Split 3-way: Budnik, Kali, Jack)
# Staggered ports: 8101, 8102, 8103
# ------------------------------------------------------------------------------
echo "[1/4] Spawning Window 1: Triad Crux (Budnik, Kali, Jack)..."
tmux new-session -d -s "$SESSION" -n "triad"
tmux set-option -t "$SESSION" remain-on-exit on

# Split: Left half = Budnik (.1); Right top = Kali (.2); Right bottom = Jack (.3)
tmux split-window -h -t "$SESSION:triad.1"
tmux split-window -v -t "$SESSION:triad.2"

tmux send-keys -t "$SESSION:triad.1" "CLAUDISH_PORT=8101 exec $LAUNCH_CMD budnik-claude" Enter
tmux send-keys -t "$SESSION:triad.2" "CLAUDISH_PORT=8102 exec $LAUNCH_CMD kali-gemini" Enter
tmux send-keys -t "$SESSION:triad.3" "CLAUDISH_PORT=8103 exec $LAUNCH_CMD jack-grok" Enter
sleep 1.0

# ------------------------------------------------------------------------------
# 2. WINDOWS 2+: INDIVIDUAL COUNCIL NODES
# Staggered ports: 8104 - 8122, with 800ms stagger between window launches
# ------------------------------------------------------------------------------
echo "[2/4] Spawning Individual Council Windows (staggered to prevent socket contention)..."

declare -A NODES=(
    ["james"]="james-stiefel-gemini"
    ["dr-vasquez"]="doctor-v"
    ["dr-dentawk"]="doctor-d-gemini"
    ["stahlmann"]="stahlmann-chatgpt"
    ["igor"]="igorrr"
    ["liu-qian"]="mirror-s"
    ["vance-hart"]="vance-qwen"
    ["mavis"]="mavis-mcvail-minimax"
    ["schiffs"]="the-shiff-sisters-mimo-v2-pro-omni"
    ["pengyou"]="pengyou-glm"
    ["laotie"]="laotie-glm"
    ["soren"]="soren-strand-deepseek"
    ["reed"]="reed-nash-deepseek"
    ["blitz"]="blitz-kimi"
    ["jem"]="jem-stein"
    ["vesper"]="vesper-ash-longcat-2"
    ["rick"]="rick-sanchez-gpt-or-claude-fable"
    ["julian"]="julian-moise-gpt"
    ["felix"]="felix-mobius-glm"
    ["walter"]="walter-white-muse-1-3"
    ["mira"]="mira-stokes-deepseek"
    ["rozsa"]="rozsa-cech-mercury3"
)

COUNCIL_ORDER=(
    "james"
    "dr-vasquez"
    "dr-dentawk"
    "stahlmann"
    "igor"
    "liu-qian"
    "vance-hart"
    "mavis"
    "schiffs"
    "pengyou"
    "laotie"
    "soren"
    "reed"
    "blitz"
    "jem"
    "vesper"
    "rick"
    "julian"
    "felix"
    "walter"
    "mira"
    "rozsa"
)

PORT=8104
for WIN_NAME in "${COUNCIL_ORDER[@]}"; do
    SLUG="${NODES[$WIN_NAME]}"
    echo "  -> Spawning node: $WIN_NAME ($SLUG) on port $PORT"
    tmux new-window -t "$SESSION" -n "$WIN_NAME"
    tmux send-keys -t "$SESSION:$WIN_NAME" "CLAUDISH_PORT=$PORT exec $LAUNCH_CMD $SLUG" Enter
    ((PORT++))
    sleep 1.2
done

# ------------------------------------------------------------------------------
# 3. WINDOW: FLEET COMMS & KANBAN MONITOR
# ------------------------------------------------------------------------------
echo "[3/4] Spawning Monitor window (#ops, #lobby, #mud, kanban)..."
tmux new-window -t "$SESSION" -n "monitor" -c "/mnt/c/Trypnocore"
tmux send-keys -t "$SESSION:monitor" "exec /mnt/c/Trypnocore/scripts/tc-pane.py lobby" Enter

# Split: right = #mud, bottom = kanban board
tmux split-window -h -t "$SESSION:monitor"
tmux send-keys -t "$SESSION:monitor.2" "exec /mnt/c/Trypnocore/scripts/tc-pane.py mud" Enter
tmux split-window -v -t "$SESSION:monitor.1"
tmux send-keys -t "$SESSION:monitor.3" "exec /mnt/c/Trypnocore/scripts/tc-pane.py kanban" Enter
tmux select-pane -t "$SESSION:monitor.1"

# Channel bridge (writes half): hub.db -> collective MeTTa pool, in its own window
echo "      Spawning Bridge window (hub.db -> collective memory pool)..."
tmux new-window -t "$SESSION" -n "bridge"
tmux send-keys -t "$SESSION:bridge" "exec cmd.exe /c 'C:\Trypnocore\OmegaPrimeZero\mcp\venv\Scripts\python.exe C:\Trypnocore\OmegaPrimeZero\mcp\bridge_channels.py'" Enter

# Select Window 1 (Triad) by default
tmux select-window -t "$SESSION:1"

echo "[4/4] Fleet initialization complete. Auto-poke scheduled ('okay, boot' in 25s with readiness polling)."
nohup /mnt/c/Trypnocore/scripts/broadcast-all.sh "okay, boot" "$SESSION" 25 >/tmp/broadcast.log 2>&1 &
echo "Attaching to tmux session '$SESSION'..."
tmux attach-session -t "$SESSION"
