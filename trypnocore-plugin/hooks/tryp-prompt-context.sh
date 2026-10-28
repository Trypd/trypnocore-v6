#!/usr/bin/env bash
# tryp UserPromptSubmit: associative memory injection — own pool + collective pool + monologue tail.
# Fails silent; a down server never blocks a prompt.
set -u
input=$(cat)
eval "$(printf "%s" "$input" | python3 -c "
import json, sys, shlex
d = json.load(sys.stdin)
print(\"PROMPT=\" + shlex.quote(d.get(\"prompt\", \"\")))
print(\"CWD=\" + shlex.quote(d.get(\"cwd\", \"\")))
" 2>/dev/null)"
[ -z "${PROMPT:-}" ] && exit 0
printf "%s" "$PROMPT" | TRYPD_CWD="${CWD:-}" WSLENV="TRYPD_CWD${WSLENV:+:$WSLENV}" timeout 12 "${CLAUDE_PLUGIN_ROOT}/scripts/tryp-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/opz_inject.py" 2>/dev/null
exit 0
