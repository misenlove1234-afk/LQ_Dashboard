@echo off
chcp 65001 > nul
title LQ All In One - 서비스 서버 (포트 8501)
cd /d "%~dp0"
echo.
echo  ============================================
echo   LQ All In One - 프로덕션 서버
echo   포트 8501 / 파일 감시 OFF (자동 재시작 없음)
echo  ============================================
echo.
streamlit run app.py --server.port 8501 --server.fileWatcherType none
pause
