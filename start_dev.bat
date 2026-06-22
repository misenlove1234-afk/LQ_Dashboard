@echo off
chcp 65001 > nul
title LQ All In One - 개발 미리보기 (포트 8502)
cd /d "%~dp0"
echo.
echo  ============================================
echo   LQ All In One - 개발 미리보기 서버
echo   포트 8502 / 파일 변경 시 자동 재시작
echo  ============================================
echo.
streamlit run app.py --server.port 8502 --server.fileWatcherType poll
pause
