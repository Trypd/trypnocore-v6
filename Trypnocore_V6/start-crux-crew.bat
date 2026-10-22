@echo off
setlocal
title Trypnocore Crux Crew
echo.
echo   TRYPNOCORE v6 - CRUX CREW LAUNCHER
echo   ==================================
echo   Boots the ops cell in its own tmux session 'cruxcrew':
echo     Budnik (Opus) - Kali (Gemini) - Jack (Grok) - Stahlmann (Codex)
echo     + monitor (lobby/mud/kanban panes) + memory bridge.
echo   Survives this window closing. Reattach from WSL: tmux attach -t cruxcrew
echo.

wsl -e bash -c "tmux has-session -t cruxcrew 2>/dev/null"
if %errorlevel%==0 (
    echo   [crew] session already running - attaching...
    echo.
    wsl -e bash -c "tmux attach-session -t cruxcrew"
    goto end
)

echo   [crew] no session - launching...
echo.
wsl -e bash -c "cd /mnt/c/Trypnocore && ./scripts/launch-cruxcrew.sh"

:end
endlocal
