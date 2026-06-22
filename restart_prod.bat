@echo off
chcp 65001 > nul
title LQ All In One - Restart Production
cd /d "%~dp0"
echo.
echo [Deploy] Stopping port 8501 process...

REM Kill only port 8501 (dev server 8502 is kept alive)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501 " ^| findstr "LISTENING" 2^>nul') do (
    echo [Deploy] Killing PID %%a ...
    taskkill /F /PID %%a 2>nul
)

timeout /t 2 /nobreak > nul
echo [Deploy] Starting production server...
start "LQ Production Server" /d "%~dp0" cmd /k "streamlit run app.py --server.port 8501 --server.fileWatcherType none"
echo [Deploy] Done. Server starting in a new window.
pause
