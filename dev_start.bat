@echo off
chcp 65001 > nul
title LQ All In One - Dev Server [8502]
cd /d "%~dp0"

echo.
echo  ============================================
echo   LQ All In One  [Dev Server / Port 8502]
echo   FileWatcher ON - auto-reload on save
echo  ============================================
echo.

streamlit run app.py --server.port 8502 --server.fileWatcherType poll

pause
