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
    echo          Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('where python') do echo [INFO] Python path: %%i
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [INFO] Python version: %%i

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found, please install Node.js 18+
    echo          Download: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('where node') do echo [INFO] Node.js path: %%i
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo [INFO] Node.js version: %%i

echo [OK] Python and Node.js ready
echo.

:: ==================== Virtual Environment ====================
echo [2/5] Configuring Python virtual environment...

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found, creating...
    echo Target path: %cd%\venv
    echo Command: python -m venv venv
    python -m venv venv 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        echo          Exit code: %errorlevel%
        echo          Possible cause: Python not properly installed, insufficient permissions, or special characters in path
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
    echo Command: pip install -r requirements.txt
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Backend dependencies installation failed
        echo          Exit code: %errorlevel%
        echo          Possible cause: Network failure, outdated pip version, or dependency version conflict
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

if not exist "frontend\node_modules\vite\" (
    echo Frontend dependencies not found, installing...
    echo Working directory: %cd%\frontend
    echo Command: npm install
    cd /d "%~dp0frontend"
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Frontend dependencies installation failed
        echo          Exit code: %errorlevel%
        echo          Possible cause: Network failure, Node.js version incompatible, or package.json configuration error
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
echo          Working directory: %~dp0
start "Taot-Backend" cmd /k "cd /d "%~dp0" && echo Activating virtual environment... && call venv\Scripts\activate.bat && echo Starting uvicorn (http://127.0.0.1:8000)... && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting frontend server (http://127.0.0.1:5173)...
echo          Working directory: %~dp0frontend
start "Taot-Frontend" cmd /k "cd /d "%~dp0frontend" && echo Starting Vite dev server... && npm run dev"

echo.
echo ============================================
echo   Start complete!
echo   Backend: http://127.0.0.1:8000
echo   Frontend: http://127.0.0.1:5173
echo ============================================
echo.
echo Press any key to close this window (backend and frontend will keep running)...
pause >nul
