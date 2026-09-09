@echo off
chcp 65001 >nul
title Taot Knowledge Base v3.1 - One-Click Start (uv)

setlocal
set "PSEXTRA="
if /i "%1"=="check" goto :checkmode
set "PSEXTRA=%*"

echo ============================================
echo   Taot Knowledge Base v3.1 - One-Click Start
echo ============================================
echo.
echo   Calls the PowerShell launcher (env check / deps / migration / all services).
echo   Pass check as first arg to run env check only.
echo   Other args (e.g. -SkipInfra) are forwarded to start.ps1.
echo.
goto :run

:checkmode
echo ============================================
echo   Taot Knowledge Base v3.1 - Env Check Mode
echo ============================================
echo.
echo   Mode: check only (no install, no start).
echo.
set "PSEXTRA=-CheckOnly -NoPause"

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %PSEXTRA%
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] start.ps1 failed, see log above.
    pause
    exit /b 1
)
endlocal
exit /b 0
