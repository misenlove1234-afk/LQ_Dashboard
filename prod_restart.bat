@echo off
chcp 65001 > nul
title LQ All In One - Restart User Server [8501]
cd /d "%~dp0"

echo.
echo  ============================================
echo   LQ All In One  [Restart User Server / 8501]
echo  ============================================
echo.

echo [1/2] Stopping port 8501...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501 " ^| findstr "LISTENING" 2^>nul') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak > nul
echo   Done.
echo.

echo [2/2] Starting user server...
echo.

streamlit run app.py --server.port 8501 --server.fileWatcherType none

pause
