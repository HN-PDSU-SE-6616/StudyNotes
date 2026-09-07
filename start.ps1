# ============================================================
#   Taot Knowledge Base v3.1 - One-Click Start (uv) [PowerShell]
#   Usage : powershell -ExecutionPolicy Bypass -File start.ps1
#   依赖   : uv (>=0.5), Node.js (>=18), Docker (可选，用于基础设施)
#   前置   : powershell -ExecutionPolicy Bypass -File .\deploy\infra.ps1
# ============================================================

$ErrorActionPreference = 'Continue'

# 项目根目录（脚本所在目录）
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }
Set-Location $ProjectRoot

$Version = 'v3.1 (uv)'

Write-Host '============================================' -ForegroundColor Cyan
Write-Host "  Taot Knowledge Base $Version - One-Click Start" -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ==================== 1/6 环境检查 ====================
Write-Host '[1/6] 检查运行环境...' -ForegroundColor Yellow

# --- uv ---
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host '[ERROR] 未找到 uv，请先安装：' -ForegroundColor Red
    Write-Host '        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' -ForegroundColor White
    Read-Host '安装完成后按 Enter 继续（或 Ctrl+C 退出）'
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCmd) { exit 1 }
}
Write-Host "[OK] uv: $(uv --version)" -ForegroundColor Green

# --- Node.js ---
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host '[ERROR] 未找到 Node.js（需 18+），请安装：https://nodejs.org/' -ForegroundColor Red
    Read-Host '安装完成后按 Enter 继续'
    exit 1
}
$nodeVersionRaw = (node --version 2>&1) -replace 'v', ''
$nodeMajor = [int]($nodeVersionRaw -split '\.')[0]
if ($nodeMajor -lt 18) {
    Write-Host '[WARNING] Node.js 版本过低（需 18+），当前：' + $nodeVersionRaw -ForegroundColor Yellow
}
Write-Host "[OK] Node.js: v$nodeVersionRaw" -ForegroundColor Green

# --- Docker 基础设施（postgres/qdrant/redis） ---
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    Write-Host '[INFO] 正在确认基础设施容器（postgres/qdrant/redis）...' -ForegroundColor White
    powershell -ExecutionPolicy Bypass -File .\deploy\infra.ps1 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[WARNING] 基础设施启动失败，请稍后手动执行：powershell -ExecutionPolicy Bypass -File .\deploy\infra.ps1' -ForegroundColor Yellow
    } else {
        Write-Host '[OK] 基础设施已就绪' -ForegroundColor Green
    }
} else {
    Write-Host '[WARNING] 未检测到 Docker，请确认 PostgreSQL/Qdrant/Redis 已由其他方式运行' -ForegroundColor Yellow
}
Write-Host ''

# ==================== 2/6 .env 与目录 ====================
Write-Host '[2/6] 检查 .env 与运行目录...' -ForegroundColor Yellow

$envFile = Join-Path $ProjectRoot '.env'
$envExampleFile = Join-Path $ProjectRoot '.env.example'
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExampleFile) {
        Copy-Item $envExampleFile $envFile
        Write-Host '[OK] .env 已由 .env.example 生成' -ForegroundColor Green
    } else {
        @'
# Taot Knowledge Base - Environment Config (auto-generated)
SECRET_KEY=change-me-in-production-use-env-var
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
DATABASE_URL=postgresql+asyncpg://taot:taot@localhost:5432/taot
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
STORAGE_ROOT=storage
'@ | Set-Content -Path $envFile -Encoding UTF8
        Write-Host '[OK] .env 已用默认配置创建' -ForegroundColor Green
    }
} else {
    Write-Host '[OK] .env 已存在' -ForegroundColor Green
}

foreach ($dir in @('uploads', 'static', 'storage')) {
    if (-not (Test-Path (Join-Path $ProjectRoot $dir))) {
        New-Item -ItemType Directory -Path (Join-Path $ProjectRoot $dir) -Force | Out-Null
    }
}
Write-Host '[OK] 运行目录就绪' -ForegroundColor Green
Write-Host ''

# ==================== 3/6 Python 依赖（uv sync） ====================
Write-Host '[3/6] 安装 Python 依赖（uv，Python 3.12）...' -ForegroundColor Yellow

$lockFile = Join-Path $ProjectRoot 'uv.lock'
if (Test-Path $lockFile) {
    Write-Host '        执行 uv sync --frozen ...' -ForegroundColor Gray
    uv sync --frozen
} else {
    Write-Host '        uv.lock 不存在，执行 uv sync ...' -ForegroundColor Gray
    uv sync
}
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] Python 依赖安装失败' -ForegroundColor Red
    Read-Host '按 Enter 退出'
    exit 1
}
Write-Host '[OK] Python 依赖就绪（uv run python --version）' -ForegroundColor Green
uv run python --version
Write-Host ''

# ==================== 4/6 数据库迁移 ====================
Write-Host '[4/6] 执行数据库迁移（alembic upgrade head）...' -ForegroundColor Yellow
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] 数据库迁移失败，请确认 PostgreSQL 已启动且 .env 正确' -ForegroundColor Red
    Read-Host '按 Enter 退出'
    exit 1
}
Write-Host '[OK] 数据库迁移完成' -ForegroundColor Green
Write-Host ''

# ==================== 5/6 前端依赖 ====================
Write-Host '[5/6] 检查前端依赖（npm）...' -ForegroundColor Yellow
$frontendPath = Join-Path $ProjectRoot 'frontend'
if (-not (Test-Path (Join-Path $frontendPath 'node_modules\vite'))) {
    Push-Location $frontendPath
    npm install
    $npmCode = $LASTEXITCODE
    Pop-Location
    if ($npmCode -ne 0) {
        Write-Host '[ERROR] 前端依赖安装失败' -ForegroundColor Red
        Read-Host '按 Enter 退出'
        exit 1
    }
    Write-Host '[OK] 前端依赖已安装' -ForegroundColor Green
} else {
    Write-Host '[OK] 前端依赖已存在' -ForegroundColor Green
}
Write-Host ''

# ==================== 6/6 启动服务 ====================
Write-Host '[6/6] 启动服务（独立窗口）...' -ForegroundColor Yellow
Write-Host ''

$backendCmd = "Set-Location '$ProjectRoot'; uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
$workerCmd  = "Set-Location '$ProjectRoot'; uv run celery -A app.worker.celery_app worker -Q parse,index -l info -P solo"
$beatCmd    = "Set-Location '$ProjectRoot'; uv run celery -A app.worker.celery_app beat -l info"
$frontCmd   = "Set-Location '$frontendPath'; npm run dev"

try {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Backend  http://127.0.0.1:8000' -ForegroundColor Cyan; $backendCmd"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Worker  (parse/index)' -ForegroundColor Cyan; $workerCmd"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Beat  (每日推荐)' -ForegroundColor Cyan; $beatCmd"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "Write-Host 'Taot-Frontend  http://127.0.0.1:5173' -ForegroundColor Cyan; $frontCmd"
} catch {
    Write-Host "[WARNING] 子窗口启动异常: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host '============================================' -ForegroundColor Cyan
Write-Host "  $Version 启动完成" -ForegroundColor Green
Write-Host '  后端 API : http://127.0.0.1:8000/api/v1' -ForegroundColor White
Write-Host '  前端     : http://127.0.0.1:5173' -ForegroundColor White
Write-Host '  接口文档 : http://127.0.0.1:8000/docs（仅本机）' -ForegroundColor White
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''
Write-Host '提示：AI 问答/个性化推荐需配置 EMBEDDING_MODEL 与 LLM_API_KEY，'
Write-Host '      并先执行 uv sync --extra ai（本地 Embedding 模型体积较大）。'
Write-Host '按 Enter 关闭本窗口（各服务窗口将保持运行）...' -ForegroundColor Yellow
Read-Host
