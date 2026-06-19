@echo off
chcp 65001 > nul
title LQ All In One - Update
echo.

:: 스크립트 폴더와 드래그된 ZIP 경로를 환경변수로 전달 (공백 경로 안전)
set "LQ_SCRIPT_DIR=%~dp0"
set "LQ_ZIP_PATH=%~1"

:: PS1 파일을 명시적 UTF-8 로 읽어 실행
:: (PowerShell 5.1 은 BOM 없는 UTF-8 파일을 ANSI 로 읽는 버그 회피)
PowerShell -ExecutionPolicy Bypass -NoProfile -Command "$d=$env:LQ_SCRIPT_DIR; $z=$env:LQ_ZIP_PATH; $f=Join-Path $d 'update.ps1'; $c=[IO.File]::ReadAllText($f,[Text.Encoding]::UTF8); &([scriptblock]::Create($c)) -ZipPath $z -ScriptDir ($d.TrimEnd('\'))"

pause
