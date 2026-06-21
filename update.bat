@echo off
chcp 65001 > nul
title LQ All In One - Update
set PYTHONIOENCODING=utf-8

if "%~1"=="" (
    python "%~dp0update.py"
) else (
    python "%~dp0update.py" "%~1"
)
