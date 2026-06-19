@echo off
chcp 65001 > nul
title LQ All In One — 자동 업데이트
echo.
PowerShell -ExecutionPolicy Bypass -NoProfile -File "%~dp0update.ps1"
pause
