@echo off
chcp 65001 > nul
title LQ All In One - Production Server (Port 8501)
cd /d "%~dp0"
echo.
echo  ============================================
echo   LQ All In One  [Production / Port 8501]
echo   FileWatcher OFF - no auto-restart
echo  ============================================
echo.
streamlit run app.py --server.port 8501 --server.fileWatcherType none
pause
