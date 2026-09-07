@echo off
chcp 65001 >nul
title Taot Knowledge Base v3.1 - One-Click Start (uv)
echo ============================================
echo   Taot Knowledge Base v3.1 - One-Click Start
echo ============================================
echo.
echo 正在调用 PowerShell 版一键脚本（uv 环境、数据库迁移、全部服务）...
echo 若本窗口策略受限，请手动执行：
echo   powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1"
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] start.ps1 执行失败，请查看上方日志。
    pause
    exit /b 1
)
