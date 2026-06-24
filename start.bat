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

:: Check Node.js major version >= 18
for /f "tokens=1 delims=v." %%v in ('node --version 2^>^&1') do (
    if %%v LSS 18 (
        echo [WARNING] Node.js version is below minimum required ^(18.x^). Please upgrade to Node.js 18+. echo          Download: https://nodejs.org/
        echo          The app may still work but some features might not be available.
        echo.
    )
)

echo [OK] Python and Node.js ready
echo.

:: ==================== Auto-create Essential Files ====================
echo [2/6] Checking essential files...

:: --- .env file ---
if not exist ".env" (
    if exist ".env.example" (
        echo         .env not found, copying from .env.example ^(default config^)...
        copy /y ".env.example" ".env" >nul
        echo [OK] .env created from .env.example
    ) else (
        echo         .env and .env.example not found, creating .env with default config...
        (
            echo # Taot Knowledge Base - Environment Config ^(auto-generated^)
            echo SECRET_KEY=change-me-in-production-use-env-var
            echo ALGORITHM=HS256
            echo ACCESS_TOKEN_EXPIRE_MINUTES=1440
            echo REFRESH_TOKEN_EXPIRE_DAYS=7
            echo DATABASE_URL=sqlite+aiosqlite:///./blog.db
            echo NOTES_DATA_PATH=data
        ) > ".env"
        echo [OK] .env created with default config
    )
) else (
    echo [OK] .env already exists, skipped
)

:: --- Required directories ---
if not exist "uploads\" (
    mkdir "uploads" 2>nul
    echo [OK] Directory created: uploads
) else (
    echo [OK] Directory exists: uploads
)
if not exist "static\" (
    mkdir "static" 2>nul
    echo [OK] Directory created: static
) else (
    echo [OK] Directory exists: static
)
echo.

:: ==================== Virtual Environment ====================
echo [3/6] Configuring Python virtual environment...

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
echo [4/6] Checking backend dependencies...

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
echo [5/6] Checking frontend dependencies...

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
echo [6/6] Starting services...
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
