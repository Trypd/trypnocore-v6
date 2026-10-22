@echo off
setlocal
title Trypnocore v6 Services
echo.
echo   TRYPNOCORE v6 - SERVICE LAUNCHER
echo   ================================
echo   Starts the two Windows-side services the fleet needs:
echo     1. OPZ memory + trinket server  (127.0.0.1:8787, supervised)
echo     2. Channel bridge               (hub.db -^> collective memory pool)
echo   The hub is serverless now (tc.py -^> hub.db) - nothing to start.
echo.

REM --- OPZ memory server: CC-WSL hooks + opz-memory MCP die without it ---
netstat -ano | findstr ":8787 " | findstr "LISTENING" >NUL 2>&1
if %errorlevel%==0 goto mem_up
echo   [memory] starting supervised OPZ server on 8787...
start "OPZ Memory" cmd /k "cd /d C:\Trypnocore\OmegaPrimeZero && python mcp\supervise.py"
goto mem_done
:mem_up
echo   [memory] already up on 8787.
:mem_done

REM --- channel bridge: feeds #lobby/#mud/#ops/kanban into the collective pool ---
tasklist /FI "WINDOWTITLE eq OPZ Bridge*" 2>NUL | findstr /I "python.exe" >NUL 2>&1
if %errorlevel%==0 goto bridge_up
echo   [bridge] starting channel bridge daemon...
start "OPZ Bridge" cmd /k "cd /d C:\Trypnocore\OmegaPrimeZero && mcp\venv\Scripts\python.exe mcp\bridge_channels.py"
goto bridge_done
:bridge_up
echo   [bridge] already running.
:bridge_done

echo.
echo   Done. This window can be closed; the services keep their own windows.
echo.
pause
endlocal
