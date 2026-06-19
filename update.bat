@echo off
chcp 65001 > nul
title LQ All In One - Update
echo.

:: 스크립트 폴더와 드래그된 ZIP 경로를 환경변수로 전달 (공백 경로 안전)
set "LQ_SCRIPT_DIR=%~dp0"
set "LQ_ZIP_PATH=%~1"

:: PS1 파일을 UTF-8 로 읽어 UTF-8 BOM 붙인 임시파일로 실행
:: (PS5.1 은 BOM 없는 UTF-8 을 ANSI 로 읽는 버그 => BOM 추가로 우회)
PowerShell -ExecutionPolicy Bypass -NoProfile -Command "$src=Join-Path $env:LQ_SCRIPT_DIR 'update.ps1'; $tmp=[IO.Path]::GetTempFileName()+'.ps1'; $c=[IO.File]::ReadAllText($src,[Text.Encoding]::UTF8); [IO.File]::WriteAllText($tmp,$c,[System.Text.UTF8Encoding]::new($true)); try{& $tmp -ZipPath $env:LQ_ZIP_PATH -ScriptDir ($env:LQ_SCRIPT_DIR.TrimEnd('\'))}finally{Remove-Item $tmp -EA 0}"

pause
