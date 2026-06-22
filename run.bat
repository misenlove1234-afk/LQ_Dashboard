@echo off
chcp 65001 > nul
title LQ All In One - 서버 실행
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo.
echo ================================================
echo   LQ All In One - 서버 실행
echo   접속 주소: http://localhost:8501
echo ================================================
echo.

:: 8501 포트 기존 프로세스 종료
echo [1/2] 기존 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8501 "') do (
    taskkill /f /pid %%a > nul 2>&1
)
echo        완료
echo.

:: Streamlit 서버 기동
echo [2/2] 서버를 시작합니다...
echo.
streamlit run app.py --server.port 8501 --server.headless false

pause
