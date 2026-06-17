# ============================================================
#   Taot Knowledge Base v2.0 - 一键启动脚本 (PowerShell)
#   用法: powershell -ExecutionPolicy Bypass -File start.ps1
# ============================================================

$ErrorActionPreference = 'Stop'

# 获取脚本所在目录作为项目根目录（所有路径基于此）
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }

Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Taot Knowledge Base v2.0 - 一键启动' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ==================== 环境检测 ====================
Write-Host '[1/5] 检测运行环境...' -ForegroundColor Yellow

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host '[错误] 未找到 Python，请安装 Python 3.9+' -ForegroundColor Red
    Write-Host '        官方下载地址: https://www.python.org/downloads/' -ForegroundColor White
    Write-Host ''
    Read-Host '安装完成后，按 Enter 键继续'
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host '[错误] 仍未检测到 Python，脚本退出' -ForegroundColor Red
        Read-Host '按 Enter 键退出'
        exit 1
    }
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host '[错误] 未找到 Node.js，请安装 Node.js 18+' -ForegroundColor Red
    Write-Host '        官方下载地址: https://nodejs.org/' -ForegroundColor White
    Write-Host ''
    Read-Host '安装完成后，按 Enter 键继续'
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        Write-Host '[错误] 仍未检测到 Node.js，脚本退出' -ForegroundColor Red
        Read-Host '按 Enter 键退出'
        exit 1
    }
}

Write-Host '[完成] Python 和 Node.js 环境就绪' -ForegroundColor Green
Write-Host ''

# ==================== 虚拟环境 ====================
Write-Host '[2/5] 配置 Python 虚拟环境...' -ForegroundColor Yellow

$venvPath = Join-Path $ProjectRoot 'venv'
$activateScript = Join-Path $venvPath 'Scripts\Activate.ps1'

if (-not (Test-Path $activateScript)) {
    Write-Host '        虚拟环境不存在，正在创建...' -ForegroundColor White
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[错误] 虚拟环境创建失败' -ForegroundColor Red
        Read-Host '按 Enter 键退出'
        exit 1
    }
    Write-Host '[完成] 虚拟环境创建成功' -ForegroundColor Green
} else {
    Write-Host '[完成] 虚拟环境已存在，跳过' -ForegroundColor Green
}

& $activateScript
Write-Host ''

# ==================== 后端依赖 ====================
Write-Host '[3/5] 检查后端依赖...' -ForegroundColor Yellow

$requirementsFile = Join-Path $ProjectRoot 'requirements.txt'
$fastapiCheck = pip show fastapi 2>$null
if (-not $fastapiCheck) {
    Write-Host '        后端依赖未安装，正在安装...' -ForegroundColor White
    pip install -r $requirementsFile -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[错误] 后端依赖安装失败' -ForegroundColor Red
        Read-Host '按 Enter 键退出'
        exit 1
    }
    Write-Host '[完成] 后端依赖安装成功' -ForegroundColor Green
} else {
    Write-Host '[完成] 后端依赖已安装，跳过' -ForegroundColor Green
}
Write-Host ''

# ==================== 前端依赖 ====================
Write-Host '[4/5] 检查前端依赖...' -ForegroundColor Yellow

$frontendPath = Join-Path $ProjectRoot 'frontend'
$nodeModulesPath = Join-Path $frontendPath 'node_modules'

if (-not (Test-Path $nodeModulesPath)) {
    Write-Host '        前端依赖未安装，正在安装（可能需要几分钟）...' -ForegroundColor White
    Push-Location $frontendPath
    npm install
    $npmExitCode = $LASTEXITCODE
    Pop-Location
    if ($npmExitCode -ne 0) {
        Write-Host '[错误] 前端依赖安装失败' -ForegroundColor Red
        Read-Host '按 Enter 键退出'
        exit 1
    }
    Write-Host '[完成] 前端依赖安装成功' -ForegroundColor Green
} else {
    Write-Host '[完成] 前端依赖已安装，跳过' -ForegroundColor Green
}
Write-Host ''

# ==================== 启动服务 ====================
Write-Host '[5/5] 启动服务...' -ForegroundColor Yellow
Write-Host ''

Write-Host '正在启动后端服务 (http://127.0.0.1:8000)...' -ForegroundColor White
Start-Process powershell `
    -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Backend - 后端服务' -ForegroundColor Cyan; & '.\venv\Scripts\Activate.ps1'; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Normal

Write-Host '正在启动前端服务 (http://127.0.0.1:5173)...' -ForegroundColor White
Start-Process powershell `
    -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Frontend - 前端服务' -ForegroundColor Cyan; npm run dev" `
    -WorkingDirectory $frontendPath `
    -WindowStyle Normal

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  启动完成！' -ForegroundColor Green
Write-Host '  后端:  http://127.0.0.1:8000' -ForegroundColor White
Write-Host '  前端:  http://127.0.0.1:5173' -ForegroundColor White
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''
Write-Host '按 Enter 键关闭此窗口（后端和前端服务将继续运行）...' -ForegroundColor Yellow
Read-Host
