@echo off
chcp 65001 >nul
title Taot Knowledge Base - One-Click Start

echo ============================================
echo   Taot Knowledge Base v2.0 - One-Click Start
echo ============================================
echo.

:: ==================== Environment Check ====================
echo [1/5] Checking environment...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found, please install Python 3.9+
    pause
    exit /b 1
)

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found, please install Node.js 18+
    pause
    exit /b 1
)

echo [OK] Python and Node.js ready
echo.

:: ==================== Virtual Environment ====================
echo [2/5] Configuring Python virtual environment...

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found, creating...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists, skipped
)

call venv\Scripts\activate.bat
echo.

:: ==================== Backend Dependencies ====================
echo [3/5] Checking backend dependencies...

pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo Backend dependencies not found, installing...
    pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [ERROR] Backend dependencies installation failed
        pause
        exit /b 1
    )
    echo [OK] Backend dependencies installed
) else (
    echo [OK] Backend dependencies already installed, skipped
)
echo.

:: ==================== Frontend Dependencies ====================
echo [4/5] Checking frontend dependencies...

if not exist "frontend\node_modules\" (
    echo Frontend dependencies not found, installing...
    cd /d "%~dp0frontend"
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Frontend dependencies installation failed
        cd /d "%~dp0"
        pause
        exit /b 1
    )
    cd /d "%~dp0"
    echo [OK] Frontend dependencies installed
) else (
    echo [OK] Frontend dependencies already installed, skipped
)
echo.

:: ==================== Start Services ====================
echo [5/5] Starting services...
echo.

echo Starting backend server (http://127.0.0.1:8000)...
start "Taot-Backend" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting frontend server (http://127.0.0.1:5173)...
start "Taot-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================
echo   Start complete!
echo   Backend: http://127.0.0.1:8000
echo   Frontend: http://127.0.0.1:5173
echo ============================================
echo.
echo Press any key to close this window (backend and frontend will keep running)...
pause >nul