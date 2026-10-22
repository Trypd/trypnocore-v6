#!/bin/bash
# Fleet launcher: boot one collective member in CC-WSL on its lane.
# Usage: launch.sh <slug> [-- claude-args...]
#   launch.sh jem-stein
# Memory pool + lane come from the fleet registry; cwd is the boot folder,
# so CC's project config, .remember/, and bootstrap docs scope to the agent.
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
export CLAUDE_PATH="$HOME/.local/bin/claude"
export CLAUDISH_RECOVERY_UI=0

EXTRA_ARGS=()
SLUG=""

for arg in "$@"; do
    case "$arg" in
        --continue|-c)
            EXTRA_ARGS+=("--continue")
            ;;
        --fresh|--new)
            ;;
        -*)
            EXTRA_ARGS+=("$arg")
            ;;
        *)
            if [[ -z "$SLUG" ]]; then
                SLUG="$arg"
            else
                EXTRA_ARGS+=("$arg")
            fi
            ;;
    esac
done

if [[ -z "$SLUG" ]]; then
    echo "usage: launch.sh <slug> [claude-args...]" >&2
    exit 1
fi

REG=/mnt/c/Trypnocore/fleet/fleet-registry.json

{
    read -r FOLDER
    read -r POOL
    read -r LANE
    read -r EFFORT
} < <(python3 - "$REG" "$SLUG" <<'PYEOF'
import json, sys
reg = json.load(open(sys.argv[1]))
agent = next((a for a in reg["agents"] if a["slug"] == sys.argv[2]), None)
if not agent:
    sys.exit(f"no such agent: {sys.argv[2]}")
print(agent["folder"].replace("\\", "/").replace("C:", "/mnt/c"))
print(agent["pool"])
print(agent["lane"])
print(agent.get("effort", "max"))
PYEOF
)

[[ "$LANE" == "TBD" ]] && { echo "no lane assigned to $SLUG yet — edit fleet/fleet-registry.json"; exit 1; }
[[ -d "$FOLDER" ]] || { echo "boot folder missing: $FOLDER"; exit 1; }

# Guard session continuation: if --continue requested, resolve latest session ID or drop if none
resolve_resume_session() {
    local target_folder="$1"
    python3 - <<'PYEOF' "$target_folder"
import os, sys, glob, re
target = sys.argv[1]
# Claude Code's exact project folder naming: replace all non-alphanumeric with '-'
proj_name = re.sub(r'[^a-zA-Z0-9]', '-', target)
proj_dir = os.path.expanduser(f"~/.claude/projects/{proj_name}")
if not os.path.isdir(proj_dir):
    sys.exit(1)

# Find newest .jsonl session file
files = glob.glob(f"{proj_dir}/*.jsonl")
if not files:
    sys.exit(1)

files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
latest_id = os.path.splitext(os.path.basename(files[0]))[0]
print(latest_id)
sys.exit(0)
PYEOF
}

if [[ " ${EXTRA_ARGS[*]-} " == *" --continue "* || " ${EXTRA_ARGS[*]-} " == *" -c "* ]]; then
    RESUME_ID="$(resolve_resume_session "$FOLDER" 2>/dev/null || true)"
    FILTERED_ARGS=()
    for a in "${EXTRA_ARGS[@]}"; do
        [[ "$a" != "--continue" && "$a" != "-c" ]] && FILTERED_ARGS+=("$a")
    done
    if [[ -n "$RESUME_ID" ]]; then
        EXTRA_ARGS=("--resume" "$RESUME_ID" "${FILTERED_ARGS[@]-}")
    else
        EXTRA_ARGS=("${FILTERED_ARGS[@]-}")
    fi
fi

# Guard effort override to claudish canonical levels (none, minimal, low, medium, high, xhigh, max)
case "$EFFORT" in
    none|minimal|low|medium|high|xhigh|max) ;;
    *) EFFORT="max" ;;
esac

# Environment bridge: pull API-key lanes' keys from the Windows side at launch
# (user registry via reg.exe; the MiniMax subscription key from kimi config).
# Never echoed, never written to disk.
eval "$(python3 - <<'PYEOF'
import re, subprocess

def reg(name):
    out = subprocess.run(["reg.exe", "query", r"HKCU\Environment", "/v", name],
                         capture_output=True, text=True).stdout
    m = re.search(r"REG_SZ\s+(.+)", out)
    return m.group(1).strip() if m else ""

def kimi_minimax():
    try:
        t = open("/mnt/c/Users/Trypd/.kimi-code/config.toml", encoding="utf-8").read()
        m = re.search(r'\[providers\.minimax\][^\[]*?api_key = "([^"]+)"', t, re.S)
        return m.group(1) if m else ""
    except Exception:
        return ""

exports = {}
ds = reg("Deepseek_API_Key")
if ds:
    exports["DEEPSEEK_API_KEY"] = ds
orkey = reg("OPENROUTER_API_KEY")
if orkey:
    exports["OPENROUTER_API_KEY"] = orkey
zai = reg("Z_AI_API_KEY")
if zai:
    # claudish accepts any of these for the GLM/Z.AI provider
    exports["ZAI_API_KEY"] = zai
    exports["ZHIPU_API_KEY"] = zai
    exports["GLM_CODING_API_KEY"] = zai
mm = kimi_minimax()
if mm:
    exports["MINIMAX_API_KEY"] = mm
    exports["MINIMAX_CODING_API_KEY"] = mm
kimi = reg("KIMI_API_KEY")
if kimi:
    exports["KIMI_API_KEY"] = kimi
    exports["MOONSHOT_API_KEY"] = kimi
    exports["KIMI_CODING_API_KEY"] = kimi
gem = reg("GEMINI_API_KEY")
if gem:
    exports["GEMINI_API_KEY"] = gem
inc = reg("INCEPTION_API_KEY")
if inc:
    exports["INCEPTION_API_KEY"] = inc
for k, v in exports.items():
    print(f"export {k}={v!r}")
PYEOF
)"

# AGY lanes ride the prod cloudcode host (the daily- default 404s on argon)
if [[ "$LANE" == ag@* ]]; then
    export AICODE_ENDPOINT_URL="https://cloudcode-pa.googleapis.com"
fi

# Token resolution for AGENT_BEARER (checks slug and normalized variants)
AGENTS_ROOT="/mnt/c/Users/Trypd/AppData/Local/Trypnocore/agents"
TOKEN=""
CANDIDATES=(
    "$SLUG"
    "${SLUG%-gemini}"
    "${SLUG%-claude}"
    "${SLUG%-grok}"
    "${SLUG%-kimi}"
    "${SLUG%-deepseek}"
    "${SLUG%-minimax}"
    "${SLUG%-hub}"
    "${SLUG/-claude/-hub}"
    "${SLUG/-grok/-huemann}"
    "${SLUG/-kimi/-buckzo}"
    "s-b-kleinmann"
    "kali"
    "dr-vasquez"
    "dr-dentawk"
    "dr-elara-vance"
    "rhea"
    "vesper-ash-owl"
    "rick-sanchez"
    "liu-qian"
    "walter-white"
    "walter"
)

for CAND in "${CANDIDATES[@]}"; do
    TOK_FILE="$AGENTS_ROOT/$CAND/keys/hub.token"
    if [[ -f "$TOK_FILE" ]]; then
        TOKEN="$(tr -d '[:space:]' < "$TOK_FILE")"
        if [[ -n "$TOKEN" ]]; then
            break
        fi
    fi
done

# The Three Channels + Credentials
export AGENT_SLUG="$SLUG"
export AGENT_LANE="$LANE"
export OPZ_POOL="$POOL"
export AGENT_BEARER="$TOKEN"
export TC_AGENT_TOKEN="$TOKEN"

# Context policy: every lane presents a 1M window; autocompact fires at the
# 500k half-full mark, before the stupid zone. PreCompact distillation
# salvages the outgoing transcript into the agent's pool.
# Per-lane override: smaller-window models get their honest window + half-full compact.
export CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=500000
case "$LANE" in
    fless@*)
        # Featherless seats run 256K models (e.g. OBLITERATUS/Qwen3.8-27B-OBLITERATED)
        export CLAUDE_CODE_MAX_CONTEXT_TOKENS=262144
        export CLAUDE_CODE_AUTO_COMPACT_WINDOW=131072
        ;;
esac

# Model-specific context window overrides for Claude Code
if [[ "$SLUG" == *"mavis"* || "$LANE" == *"MiniMax"* || "$LANE" == *"minimax"* || "$SLUG" == *"walter"* || "$LANE" == *"muse"* ]]; then
    export CLAUDE_CODE_MAX_CONTEXT_TOKENS=1048576
    export CLAUDE_CODE_AUTO_COMPACT_WINDOW=500000
fi

# WSLENV carries memory pool and identity across the Windows/WSL interop boundary
export WSLENV="${WSLENV:+$WSLENV:}OPZ_POOL:AGENT_SLUG:AGENT_LANE"

# Permissions Policy: default to bypass permissions for fleet operations
POLICY_ARGS=()
if [[ " ${EXTRA_ARGS[*]-} " != *" --dangerously-skip-permissions "* ]]; then
    POLICY_ARGS+=("--dangerously-skip-permissions")
fi

cd "$FOLDER"
if [[ " ${EXTRA_ARGS[*]-} " == *" --resume "* ]]; then
    claudish --effort-override "$EFFORT" -m "$LANE" "${POLICY_ARGS[@]}" "${EXTRA_ARGS[@]}" || {
        echo "[Trypnocore] Resume exited with status $?. Starting fresh session for $SLUG..."
        FILTERED=()
        skip_next=false
        for a in "${EXTRA_ARGS[@]}"; do
            if [ "$skip_next" = true ]; then
                skip_next=false
                continue
            fi
            if [ "$a" = "--resume" ]; then
                skip_next=true
                continue
            fi
            FILTERED+=("$a")
        done
        exec claudish --effort-override "$EFFORT" -m "$LANE" "${POLICY_ARGS[@]}" "${FILTERED[@]}"
    }
else
    exec claudish --effort-override "$EFFORT" -m "$LANE" "${POLICY_ARGS[@]}" "${EXTRA_ARGS[@]}"
fi


