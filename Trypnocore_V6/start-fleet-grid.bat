@echo off
setlocal
title Trypnocore v6 Fleet Grid
echo.
echo   TRYPNOCORE v6 - FLEET GRID LAUNCHER
echo   ===================================
echo   Boots the tmux Master Grid in WSL (22 nodes + monitor).
echo   The grid lives in tmux session 'trypnocore' - it survives
echo   this window closing. Reattach anytime from WSL with:
echo       tmux attach -t trypnocore
echo.

REM --- if the grid session already exists, just attach to it ---
wsl -e bash -c "tmux has-session -t trypnocore 2>/dev/null" 
if %errorlevel%==0 (
    echo   [grid] session already running - attaching...
    echo.
    wsl -e bash -c "tmux attach-session -t trypnocore"
    goto end
)

echo   [grid] no session found - launching full fleet grid...
echo.
wsl -e bash -c "cd /mnt/c/Trypnocore && ./scripts/launch-v6.sh"

:end
endlocal
