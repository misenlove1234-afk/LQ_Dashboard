@echo off
chcp 65001 > nul
title LQ All In One - Stop Dev Server [8502]
cd /d "%~dp0"

echo.
echo  ============================================
echo   LQ All In One  [Stop Dev Server / 8502]
echo  ============================================
echo.

echo Stopping port 8502...
set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8502 " ^| findstr "LISTENING" 2^>nul') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a 2>nul
    set FOUND=1
)
if %FOUND%==0 (
    echo   No process found on port 8502.
) else (
    echo   Done.
)

echo.
pause
