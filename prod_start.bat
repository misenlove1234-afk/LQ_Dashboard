@echo off
chcp 65001 > nul
title LQ All In One - User Server [8501]
cd /d "%~dp0"

echo.
echo  ============================================
echo   LQ All In One  [User Server / Port 8501]
echo   FileWatcher OFF
echo  ============================================
echo.

streamlit run app.py --server.port 8501 --server.fileWatcherType none

pause
