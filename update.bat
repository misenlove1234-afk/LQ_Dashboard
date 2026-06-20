@echo off
chcp 65001 > nul
title LQ All In One - Update
echo.

if "%~1"=="" (
    PowerShell -ExecutionPolicy Bypass -NoProfile -File "%~dp0update.ps1"
) else (
    PowerShell -ExecutionPolicy Bypass -NoProfile -File "%~dp0update.ps1" -ZipPath "%~1"
)

pause
