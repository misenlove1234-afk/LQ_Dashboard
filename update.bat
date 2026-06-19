@echo off
chcp 65001 > nul
title LQ All In One — 자동 업데이트
echo.

if "%~1"=="" (
    :: 직접 실행 — Downloads 폴더에서 ZIP 자동 탐색
    PowerShell -ExecutionPolicy Bypass -NoProfile -File "%~dp0update.ps1"
) else (
    :: ZIP 파일을 드래그 앤 드랍으로 전달
    PowerShell -ExecutionPolicy Bypass -NoProfile -File "%~dp0update.ps1" -ZipPath "%~1"
)
pause
