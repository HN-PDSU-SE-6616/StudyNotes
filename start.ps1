# ============================================================
#   Taot 知识库 - 一键启动/环境自检 (uv) [PowerShell]
#
#   用法：
#     powershell -ExecutionPolicy Bypass -File start.ps1            # 环境准备 + 启动全部服务
#     powershell -ExecutionPolicy Bypass -File start.ps1 -CheckOnly # 只做环境自检（CI/排障用）
#     powershell -ExecutionPolicy Bypass -File start.ps1 -NoPause   # 完成后不等待按键
#
#   依赖：uv(>=0.5)、Node.js(>=18)、Docker(可选，用于基础服务容器)
#   行为：自检 → 基础服务(infra.ps1) → .env/目录 → uv sync → 数据库迁移
#         → 前端依赖 → 分别弹出 后端/Worker/Beat/前端 四个窗口
#   说明：控制台输出使用 ASCII（规避 Windows PowerShell 5.1 对无 BOM UTF-8 的中文误读）。
# ============================================================
param(
    [switch]$CheckOnly,   # 仅环境自检，不执行安装/启动
    [switch]$NoPause,     # 运行完不 Read-Host 等待
    [switch]$SkipInfra    # 跳过 3/6 基础服务容器段（自行管理基础设施时使用）
)

$ErrorActionPreference = 'Continue'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location $ProjectRoot
$Version = 'v3.1 (uv)'

function Say([string]$text, [string]$color = 'White') {
    Write-Host $text -ForegroundColor $color
}
function Ok([string]$text) { Say "[OK] $text" Green }
function Warn([string]$text) { Say "[WARN] $text" Yellow }
function Fail([string]$text) { Say "[ERROR] $text" Red }

function Test-Command([string]$name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Test-PortListen([int]$port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

$modeLabel = if ($CheckOnly) { 'ENV CHECK' } else { 'ONE-CLICK START' }
Say '============================================' Cyan
Say "  Taot Knowledge Base $Version - $modeLabel" Cyan
Say '============================================' Cyan
Say ''

# ==================== 1/6 运行环境检查 ====================
Say '[1/6] Checking runtime environment...' Yellow

$problems = @()
if (-not (Test-Command uv))   { $problems += 'not found: uv (install: irm https://astral.sh/uv/install.ps1 | iex)' }
if (-not (Test-Command node)) { $problems += 'not found: Node.js 18+ (https://nodejs.org/)' }
if (-not (Test-Command npm))  { $problems += 'not found: npm (shipped with Node.js)' }
if ($problems.Count -gt 0) {
    foreach ($p in $problems) { Fail $p }
    if (-not $CheckOnly) { Read-Host 'Press Enter to exit' }
    exit 1
}
Ok "uv: $(uv --version)"
Ok "Node.js: $(node --version)"
if (Test-Command docker) { Ok "docker: $(docker --version)" } else { Warn 'not found: docker (need PostgreSQL/Redis/Qdrant from elsewhere)' }

# ==================== 2/6 .env 与运行目录 ====================
Say '[2/6] Checking .env and runtime dirs...' Yellow
$envFile = Join-Path $ProjectRoot '.env'
$envExampleFile = Join-Path $ProjectRoot '.env.example'
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExampleFile) {
        Copy-Item $envExampleFile $envFile
        Ok '.env created from .env.example (edit keys/models as needed)'
    } else {
        Fail 'missing .env.example, cannot generate .env'
        exit 1
    }
}
# 常见配置错误预检（避免 alembic/uvicorn 启动期才崩溃）
$envText = Get-Content -Raw -Path $envFile
if ($envText -notmatch 'CORS_ORIGINS\s*=\s*\[') {
    Fail '.env CORS_ORIGINS must be a JSON array string, e.g. CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]'
    exit 1
}
if (($envText -notmatch 'EMBEDDING_PROVIDER\s*=\s*api') -and
    ($envText -match 'EMBEDDING_BASE_URL') -and ($envText -match 'EMBEDDING_API_KEY')) {
    Warn 'remote Embedding env detected but EMBEDDING_PROVIDER=api is missing (explicit provider wins)'
}
foreach ($dir in @('uploads', 'static', 'storage')) {
    if (-not (Test-Path (Join-Path $ProjectRoot $dir))) {
        New-Item -ItemType Directory -Path (Join-Path $ProjectRoot $dir) -Force | Out-Null
    }
}
Ok '.env and runtime dirs ready'

# 端口占用提示（不影响继续）
foreach ($item in @(@{Port=5432;Name='PostgreSQL'}, @{Port=6333;Name='Qdrant'},
                    @{Port=6379;Name='Redis'}, @{Port=6080;Name='Embedding'},
                    @{Port=8000;Name='Backend'}, @{Port=5173;Name='Frontend'})) {
    if (Test-PortListen $item.Port) { Ok "$($item.Name) :$($item.Port) is listening" }
    else { Warn "$($item.Name) :$($item.Port) NOT listening" }
}

if ($CheckOnly) {
    Say '--------------------------------------------' Cyan
    Say '  [CheckOnly] env check finished.' Green
    Say '  8000/5173 NOT listening is expected (apps not started).' White
    exit 0
}

# ==================== 3/6 基础服务容器（已运行则跳过） ====================
Say '[3/6] Ensuring infra containers (infra.ps1)...' Yellow
$infraPorts = @(5432, 6379, 6333)          # postgres / redis / qdrant (app 必需)
$infraUp = ($infraPorts | Where-Object { Test-PortListen $_ }).Count -eq $infraPorts.Count
if ($SkipInfra) {
    Ok '-SkipInfra given: skip infra section'
} elseif ($infraUp) {
    Ok 'infra ports 5432/6379/6333 already listening: skip infra.ps1'
} elseif (Test-Command docker) {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot 'deploy\infra.ps1')
    if ($LASTEXITCODE -ne 0) { Warn 'infra.ps1 partially failed; run deploy\infra.ps1 manually later' }
    else { Ok 'infra containers ready' }
} else {
    Warn 'no docker: make sure PostgreSQL/Redis/Qdrant are provided otherwise'
}

# ==================== 4/6 Python 依赖 ====================
Say '[4/6] Installing Python deps (uv sync)...' Yellow
if (Test-Path (Join-Path $ProjectRoot 'uv.lock')) {
    uv sync --frozen
} else {
    uv sync
}
if ($LASTEXITCODE -ne 0) { Fail 'uv sync failed'; Read-Host 'Press Enter to exit'; exit 1 }
Ok 'Python deps ready'

# ==================== 5/6 数据库迁移 ====================
Say '[5/6] Running DB migration (alembic upgrade head)...' Yellow
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail 'alembic upgrade failed (check PostgreSQL & .env)'; Read-Host 'Press Enter to exit'; exit 1 }
Ok 'database migration done'

# ==================== 6/6 前端依赖与启动 ====================
Say '[6/6] Frontend deps and service startup...' Yellow
$frontendPath = Join-Path $ProjectRoot 'frontend'
if (-not (Test-Path (Join-Path $frontendPath 'node_modules\vite'))) {
    Push-Location $frontendPath
    npm install
    $npmCode = $LASTEXITCODE
    Pop-Location
    if ($npmCode -ne 0) { Fail 'npm install failed'; Read-Host 'Press Enter to exit'; exit 1 }
    Ok 'frontend deps installed'
}

# 已运行检测：端口监听（backend/frontend），或命令行匹配（celery worker/beat）
function Test-CeleryRunning([string]$kind) {
    return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'celery_app' -and $_.CommandLine -match $kind })
}
# 直启进程：-ArgumentList 数组由 Start-Process 自行转义，避免嵌套 powershell -Command 拼接被引号破坏
function Start-TaotProc([string]$file, [string[]]$argList, [string]$dir) {
    if (-not (Test-Path $file)) { Warn "launcher not found: $file"; return }
    Start-Process -FilePath $file -ArgumentList $argList -WorkingDirectory $dir | Out-Null
}
$uvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uvExe) { $uvExe = 'uv.exe' }
$npmExe = Join-Path (Split-Path (Get-Command npm -ErrorAction SilentlyContinue).Source) 'npm.cmd'
if (-not (Test-Path $npmExe)) { $npmExe = 'npm.cmd' }

# 幂等启动：已运行则跳过（修复重复启动导致端口二次绑定 WinError 10013 / EADDRINUSE）
if (Test-PortListen 8000) { Ok 'backend :8000 already listening, skip launch' }
else { Start-TaotProc $uvExe @('run','uvicorn','app.main:app','--reload','--host','127.0.0.1','--port','8000') $ProjectRoot }
if (Test-CeleryRunning 'worker') { Ok 'celery worker already running, skip launch' }
else { Start-TaotProc $uvExe @('run','celery','-A','app.worker.celery_app','worker','-Q','parse,index','-l','info','-P','solo') $ProjectRoot }
if (Test-CeleryRunning 'beat') { Ok 'celery beat already running, skip launch' }
else { Start-TaotProc $uvExe @('run','celery','-A','app.worker.celery_app','beat','-l','info') $ProjectRoot }
if (Test-PortListen 5173) { Ok 'frontend :5173 already listening, skip launch' }
else { Start-TaotProc $npmExe @('run','dev') $frontendPath }

Say '============================================' Cyan
Say "  $Version started" Green
Say '  Backend API : http://127.0.0.1:8000/api/v1 (docs /docs local only)' White
Say '  Frontend    : http://127.0.0.1:5173' White
Say '  Metrics     : http://127.0.0.1:8000/metrics (for Prometheus)' White
Say '  Monitoring  : http://localhost:3000 (deploy/monitoring, docker compose up -d)' White
Say '============================================' Cyan
Say ''
Say 'LLM/Embedding come from .env; Embedding defaults to in-container bge-small-zh (6080).' Yellow
if (-not $NoPause) { Read-Host 'Press Enter to close this window (4 service windows stay running)' }
