@echo off
chcp 65001 > nul
title LQ All In One - Update
echo.

:: %~dp0 (BAT 파일 폴더, 후행 \ 포함)과 %~1 (드래그된 ZIP 경로)를
:: PowerShell 명령 문자열 안에 cmd.exe 가 직접 삽입 -- 환경변수 미사용
PowerShell -ExecutionPolicy Bypass -NoProfile -Command "$src='%~dp0update.ps1'; $tmp=[IO.Path]::GetTempFileName()+'.ps1'; $c=[IO.File]::ReadAllText($src,[Text.Encoding]::UTF8); [IO.File]::WriteAllText($tmp,$c,[System.Text.UTF8Encoding]::new($true)); try{& $tmp -ZipPath '%~1' -ScriptDir '%~dp0'}finally{Remove-Item $tmp -EA 0}"

pause
