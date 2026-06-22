@echo off
chcp 65001 > nul
title LQ All In One - Stop User Server [8501]
cd /d "%~dp0"

echo.
echo  ============================================
echo   LQ All In One  [Stop User Server / 8501]
echo  ============================================
echo.

echo Stopping port 8501...
set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501 " ^| findstr "LISTENING" 2^>nul') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a 2>nul
    set FOUND=1
)
if %FOUND%==0 (
    echo   No process found on port 8501.
) else (
    echo   Done.
)

echo.
pause
