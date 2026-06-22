@echo off
chcp 65001 > nul
title LQ All In One - 프로덕션 재시작
cd /d "%~dp0"
echo.
echo [배포] 프로덕션 서버를 재시작합니다...
echo [배포] 기존 8501 포트 프로세스를 종료합니다.

REM 8501 포트를 사용하는 프로세스만 종료 (개발 서버 8502는 유지)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501 " ^| findstr "LISTENING"') do (
    echo [배포] PID %%a 종료 중...
    taskkill /F /PID %%a 2>nul
)

timeout /t 2 /nobreak > nul
echo [배포] 프로덕션 서버를 다시 시작합니다...
start "LQ 프로덕션 서버" cmd /k "cd /d "%~dp0" && streamlit run app.py --server.port 8501 --server.fileWatcherType none"
echo [배포] 완료. 새 창에서 서버가 시작됩니다.
pause
