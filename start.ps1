# ============================================================
#   Taot Knowledge Base v2.0 - One-Click Start (PowerShell)
#   Usage: powershell -ExecutionPolicy Bypass -File start.ps1
# ============================================================

$ErrorActionPreference = 'Continue'

# Get script directory as project root (all paths based on this)
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }

Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Taot Knowledge Base v2.0 - One-Click Start' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ==================== Environment Check ====================
Write-Host '[1/5] Checking environment...' -ForegroundColor Yellow

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host '[ERROR] Python not found, please install Python 3.9+' -ForegroundColor Red
    Write-Host '         Download: https://www.python.org/downloads/' -ForegroundColor White
    Write-Host ''
    Read-Host 'After installation, press Enter to continue'
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host '[ERROR] Python still not found, exiting' -ForegroundColor Red
        Read-Host 'Press Enter to exit'
        exit 1
    }
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host '[ERROR] Node.js not found, please install Node.js 18+' -ForegroundColor Red
    Write-Host '         Download: https://nodejs.org/' -ForegroundColor White
    Write-Host ''
    Read-Host 'After installation, press Enter to continue'
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        Write-Host '[ERROR] Node.js still not found, exiting' -ForegroundColor Red
        Read-Host 'Press Enter to exit'
        exit 1
    }
}

# Verify Node.js version >= 18
$nodeVersionRaw = (node --version 2>&1) -replace 'v', ''
$nodeMajor = [int]($nodeVersionRaw -split '\.')[0]
if ($nodeMajor -lt 18) {
    Write-Host "[WARNING] Node.js version $($nodeCmd.Version) is below minimum required (18.x). Please upgrade to Node.js 18+ for full compatibility." -ForegroundColor Yellow
    Write-Host '           Download: https://nodejs.org/' -ForegroundColor White
    Write-Host '           The app may still work but some features might not be available.' -ForegroundColor Yellow
    Write-Host ''
}

Write-Host "Python path: $($pythonCmd.Source)" -ForegroundColor Gray
Write-Host "Python version: $($pythonCmd.Version)" -ForegroundColor Green
Write-Host "Node.js path: $($nodeCmd.Source)" -ForegroundColor Gray
Write-Host "Node.js version: $($nodeCmd.Version)" -ForegroundColor Green
Write-Host '[OK] Python and Node.js ready' -ForegroundColor Green
Write-Host ''

# ==================== Auto-create Essential Files ====================
Write-Host '[2/6] Checking essential files...' -ForegroundColor Yellow

# --- .env file ---
$envFile = Join-Path $ProjectRoot '.env'
$envExampleFile = Join-Path $ProjectRoot '.env.example'
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExampleFile) {
        Write-Host '        .env not found, copying from .env.example (default config)...' -ForegroundColor White
        Copy-Item $envExampleFile $envFile
        Write-Host "[OK] .env created from .env.example (path: $envFile)" -ForegroundColor Green
    } else {
        Write-Host '        .env and .env.example not found, creating .env with default config...' -ForegroundColor White
        $defaultEnv = @'
# Taot Knowledge Base - Environment Config (auto-generated)
SECRET_KEY=change-me-in-production-use-env-var
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
DATABASE_URL=sqlite+aiosqlite:///./blog.db
NOTES_DATA_PATH=data
'@
        Set-Content -Path $envFile -Value $defaultEnv -Encoding UTF8
        Write-Host "[OK] .env created with default config (path: $envFile)" -ForegroundColor Green
    }
} else {
    Write-Host "[OK] .env already exists, skipping (path: $envFile)" -ForegroundColor Green
}

# --- Required directories ---
$requiredDirs = @('uploads', 'static')
foreach ($dir in $requiredDirs) {
    $dirPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $dirPath)) {
        New-Item -ItemType Directory -Path $dirPath -Force | Out-Null
        Write-Host "[OK] Directory created: $dir" -ForegroundColor Green
    } else {
        Write-Host "[OK] Directory exists: $dir" -ForegroundColor Green
    }
}

Write-Host ''

# ==================== Virtual Environment ====================
Write-Host '[3/6] Configuring Python virtual environment...' -ForegroundColor Yellow

$venvPath = Join-Path $ProjectRoot 'venv'
$activateScript = Join-Path $venvPath 'Scripts\Activate.ps1'

if (-not (Test-Path $activateScript)) {
    Write-Host "        Virtual environment not found, creating (target: $venvPath)..." -ForegroundColor White
    Write-Host "        Command: python -m venv $venvPath" -ForegroundColor Gray
    $venvOutput = python -m venv $venvPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] Failed to create virtual environment' -ForegroundColor Red
        Write-Host "        Exit code: $LASTEXITCODE" -ForegroundColor Red
        if ($venvOutput) {
            Write-Host '        Error details:' -ForegroundColor Red
            Write-Host $venvOutput -ForegroundColor Red
        }
        Write-Host '        Possible cause: Python not properly installed, insufficient permissions, or special characters in path' -ForegroundColor Yellow
        Read-Host 'Press Enter to exit'
        exit 1
    }
    Write-Host '[OK] Virtual environment created' -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment already exists, skipping (path: $venvPath)" -ForegroundColor Green
}

& $activateScript
Write-Host ''

# ==================== Backend Dependencies ====================
Write-Host '[4/6] Checking backend dependencies...' -ForegroundColor Yellow

$requirementsFile = Join-Path $ProjectRoot 'requirements.txt'
$fastapiCheck = pip show fastapi 2>$null
if (-not $fastapiCheck) {
    Write-Host "        Backend dependencies not installed, installing from $requirementsFile..." -ForegroundColor White
    Write-Host "        Command: pip install -r $requirementsFile" -ForegroundColor Gray
    $pipOutput = pip install -r $requirementsFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] Backend dependencies installation failed' -ForegroundColor Red
        Write-Host "        Exit code: $LASTEXITCODE" -ForegroundColor Red
        if ($pipOutput) {
            Write-Host '        Error details (last 20 lines):' -ForegroundColor Red
            $errorLines = $pipOutput | Select-Object -Last 20
            Write-Host ($errorLines -join "`n") -ForegroundColor Red
        }
        Write-Host '        Possible cause: Network failure, outdated pip version, or dependency version conflict' -ForegroundColor Yellow
        Read-Host 'Press Enter to exit'
        exit 1
    }
    Write-Host '[OK] Backend dependencies installed' -ForegroundColor Green
} else {
    Write-Host '[OK] Backend dependencies already installed, skipping' -ForegroundColor Green
}
Write-Host ''

# ==================== Frontend Dependencies ====================
Write-Host '[5/6] Checking frontend dependencies...' -ForegroundColor Yellow

$frontendPath = Join-Path $ProjectRoot 'frontend'
$nodeModulesPath = Join-Path $frontendPath 'node_modules'

$viteModulePath = Join-Path $frontendPath 'node_modules\vite'
$depsInstalled = Test-Path $viteModulePath

if (-not $depsInstalled) {
    Write-Host "        Frontend dependencies not installed, installing (working dir: $frontendPath, may take a few minutes)..." -ForegroundColor White
    Write-Host '        Command: npm install' -ForegroundColor Gray
    Push-Location $frontendPath
    $npmOutput = npm install 2>&1
    $npmExitCode = $LASTEXITCODE
    Pop-Location
    if ($npmExitCode -ne 0) {
        Write-Host '[ERROR] Frontend dependencies installation failed' -ForegroundColor Red
        Write-Host "        Exit code: $npmExitCode" -ForegroundColor Red
        if ($npmOutput) {
            Write-Host '        Error details (last 20 lines):' -ForegroundColor Red
            $errorLines = $npmOutput | Select-Object -Last 20
            Write-Host ($errorLines -join "`n") -ForegroundColor Red
        }
        Write-Host '        Possible cause: Network failure, Node.js version incompatible, or package.json configuration error' -ForegroundColor Yellow
        Read-Host 'Press Enter to exit'
        exit 1
    }
    Write-Host '[OK] Frontend dependencies installed' -ForegroundColor Green
} else {
    Write-Host "[OK] Frontend dependencies already installed, skipping (path: $viteModulePath)" -ForegroundColor Green
}
Write-Host ''

# ==================== Start Services ====================
Write-Host '[6/6] Starting services...' -ForegroundColor Yellow
Write-Host ''

Write-Host 'Starting backend server (http://127.0.0.1:8000)...' -ForegroundColor White
Write-Host "        Working directory: $ProjectRoot" -ForegroundColor Gray
try {
    $backendProcess = Start-Process powershell `
        -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Backend - Backend Service' -ForegroundColor Cyan; Write-Host 'Activating virtual environment...' -ForegroundColor Gray; & '.\venv\Scripts\Activate.ps1'; Write-Host 'Starting uvicorn (http://127.0.0.1:8000)...' -ForegroundColor Gray; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Normal `
        -PassThru
    Write-Host "        Backend process started (PID: $($backendProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Backend service start exception: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host 'Starting frontend server (http://127.0.0.1:5173)...' -ForegroundColor White
Write-Host "        Working directory: $frontendPath" -ForegroundColor Gray
try {
    $frontendProcess = Start-Process powershell `
        -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Frontend - Frontend Service' -ForegroundColor Cyan; npm run dev" `
        -WorkingDirectory $frontendPath `
        -WindowStyle Normal `
        -PassThru
    Write-Host "        Frontend process started (PID: $($frontendProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Frontend service start exception: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Start complete!' -ForegroundColor Green
Write-Host '  Backend:  http://127.0.0.1:8000' -ForegroundColor White
Write-Host '  Frontend: http://127.0.0.1:5173' -ForegroundColor White
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Press Enter to close this window (backend and frontend will keep running)...' -ForegroundColor Yellow
Read-Host
