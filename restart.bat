@echo off
chcp 65001 > nul
title LQ All In One - 재실행
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo.
echo ================================================
echo   LQ All In One - 코드 수정 후 재실행
echo   접속 주소: http://localhost:8501
echo ================================================
echo.

:: 8501 포트 기존 프로세스 종료
echo [1/3] 기존 서버 종료 중...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8501 "') do (
    taskkill /f /pid %%a > nul 2>&1
)
echo        완료
echo.

:: __pycache__ 삭제 (캐시 초기화)
echo [2/3] 캐시 초기화 중...
for /d /r "%~dp0" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
echo        완료
echo.

:: Streamlit 서버 재기동
echo [3/3] 서버를 재시작합니다...
echo.
streamlit run app.py --server.port 8501 --server.headless false

pause
