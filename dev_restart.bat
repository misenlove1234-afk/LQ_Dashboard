@echo off
chcp 65001 > nul
title LQ All In One - Restart Dev Server [8502]
cd /d "%~dp0"

echo.
echo  ============================================
echo   LQ All In One  [Restart Dev Server / 8502]
echo   FileWatcher ON - auto-reload on save
echo  ============================================
echo.

echo [1/2] Stopping port 8502...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8502 " ^| findstr "LISTENING" 2^>nul') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak > nul
echo   Done.
echo.

echo [2/2] Starting dev server...
echo.

streamlit run app.py --server.port 8502 --server.fileWatcherType poll

pause
