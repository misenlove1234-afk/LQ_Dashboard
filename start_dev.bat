@echo off
chcp 65001 > nul
title LQ All In One - Dev Preview (Port 8502)
cd /d "%~dp0"
echo.
echo  ============================================
echo   LQ All In One  [Dev Preview / Port 8502]
echo   FileWatcher ON - auto-restart on change
echo  ============================================
echo.

REM Kill any existing process on port 8502 before starting
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8502 " ^| findstr "LISTENING" 2^>nul') do (
    echo [Dev] Releasing port 8502 (PID %%a)...
    taskkill /F /PID %%a 2>nul
)

streamlit run app.py --server.port 8502 --server.fileWatcherType poll
pause
