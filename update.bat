@echo off
chcp 65001 > nul
title LQ All In One - Update
echo.
PowerShell -ExecutionPolicy Bypass -NoProfile -File "%~dp0update.ps1" -ZipPath "%~1"
pause
