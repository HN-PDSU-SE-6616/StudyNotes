# ============================================================
#   Taot 知识库 — 独立基础服务容器编排（幂等，可重复执行）
#
#   职责：确保 PostgreSQL / Redis / Qdrant / MySQL 以独立容器
#         运行于外部网络 taot-net（应用栈用 docker compose 编排，
#         compose down 不影响本脚本管理的容器与数据卷）。
#
#   环境感知：
#     - 同名容器已存在 → 直接复用并保证已连入 taot-net；
#     - 目标宿主端口已被【非本项目容器/本机服务】占用 →
#       跳过创建并给出提示（可改用本机服务：调整连接地址即可，
#       不重复创建容器）。
#
#   用法：
#     powershell -ExecutionPolicy Bypass -File deploy/infra.ps1   # 全量 Ensure
#     powershell -ExecutionPolicy Bypass -File deploy/infra.ps1 -OnlyMysql  # 补建 MySQL
# ============================================================

param(
    [switch]$OnlyMysql
)

$ErrorActionPreference = 'Continue'
$Net = 'taot-net'
$Pw = 'taot'
$PgDataVol = 'taot-kb_pg_data'      # 沿用原 compose 数据卷，避免重建丢数据
$RedisDataVol = 'taot-kb_redis_data'
$MysqlDataVol = 'taot_mysql_data'

Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Taot 基础服务独立容器 Ensure (infra.ps1)' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan

# ---------- 外部网络 ----------
function Ensure-Network {
    $exists = docker network ls --format '{{.Name}}' 2>$null | Select-String -SimpleMatch $Net
    if (-not $exists) {
        Write-Host "[NET] 创建外部网络 $Net ..." -ForegroundColor Yellow
        docker network create $Net | Out-Null
    }
    Write-Host "[NET] 网络 $Net 就绪" -ForegroundColor Green
}

# ---------- 容器帮助 ----------
function Test-ContainerExists([string]$name) {
    return [bool](docker ps -a --format '{{.Names}}' 2>$null | Select-String -Pattern "^$name$")
}

function Start-IfStopped([string]$name) {
    $state = docker inspect -f '{{.State.Status}}' $name 2>$null
    if ($state -eq 'exited' -or $state -eq 'created') {
        Write-Host "[$name] 容器存在但未运行，启动中..." -ForegroundColor Yellow
        docker start $name | Out-Null
    }
}

# 仅认可本脚本创建的容器（避免误复用外部同名 postgres/redis/mysql）
function Test-IsTaot([string]$name) {
    $lbl = docker inspect -f '{{index .Config.Labels "com.taot.infra"}}' $name 2>$null
    return ($lbl -eq 'true')
}

function Ensure-NetConnect([string]$name) {
    # 容器不在 taot-net 时连接（已在则跳过）
    $json = docker inspect -f '{{json .NetworkSettings.Networks}}' $name 2>$null
    if ($json -notmatch $Net) {
        docker network connect $Net $name 2>$null
        Write-Host "[$name] 已连接 $Net" -ForegroundColor Green
    } else {
        Write-Host "[$name] 已位于 $Net" -ForegroundColor Green
    }
}

function Test-HostPortFree([int]$port) {
    # 端口被本机服务或其它容器占用（0.0.0.0/:: 监听）
    $busy = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @('0.0.0.0', '::', '[::]') -or $_.LocalAddress -notmatch '^(127\.|::1)' }
    return -not [bool]$busy
}

# ---------- PostgreSQL ----------
function Ensure-Postgres {
    if (Test-ContainerExists 'postgres') {
        if (-not (Test-IsTaot 'postgres')) {
            Write-Host '[postgres] 存在外部同名容器 postgres，跳过创建（请自行管理连接）。' -ForegroundColor Yellow
            return
        }
        Start-IfStopped 'postgres'
        Ensure-NetConnect 'postgres'
        Write-Host '[postgres] 复用已有容器 postgres' -ForegroundColor Green
        return
    }
    if (-not (Test-HostPortFree 5432)) {
        Write-Host '[postgres] 5432 已被本机/其它服务占用：跳过创建。' -ForegroundColor Yellow
        Write-Host '          若改用本机 PostgreSQL，请同步修改 .env 中 DATABASE_URL 连接地址。' -ForegroundColor Gray
        return
    }
    Write-Host '[postgres] 创建独立容器 postgres（数据卷复用 taot-kb_pg_data）...' -ForegroundColor Yellow
    docker run -d --name postgres --network $Net `
        --label com.taot.infra=true `
        -v "${PgDataVol}:/var/lib/postgresql/data" `
        -p 5432:5432 `
        -e POSTGRES_USER=taot -e POSTGRES_PASSWORD=$Pw -e POSTGRES_DB=taot `
        --restart unless-stopped postgres:16-alpine | Out-Null
}

# ---------- Redis ----------
function Ensure-Redis {
    if (Test-ContainerExists 'redis') {
        if (-not (Test-IsTaot 'redis')) {
            Write-Host '[redis] 存在外部同名容器 redis，跳过创建（请自行管理连接）。' -ForegroundColor Yellow
            return
        }
        Start-IfStopped 'redis'
        Ensure-NetConnect 'redis'
        Write-Host '[redis] 复用已有容器 redis' -ForegroundColor Green
        return
    }
    if (-not (Test-HostPortFree 6379)) {
        Write-Host '[redis] 6379 已被本机/其它服务占用：跳过创建。' -ForegroundColor Yellow
        return
    }
    Write-Host '[redis] 创建独立容器 redis（数据卷复用 taot-kb_redis_data）...' -ForegroundColor Yellow
    docker run -d --name redis --network $Net `
        --label com.taot.infra=true `
        -v "${RedisDataVol}:/data" `
        -p 6379:6379 `
        --restart unless-stopped redis:7-alpine redis-server --appendonly yes | Out-Null
}

# ---------- Qdrant（复用现有独立容器） ----------
function Ensure-Qdrant {
    if (Test-ContainerExists 'qdrant') {
        Start-IfStopped 'qdrant'
        Ensure-NetConnect 'qdrant'
        Write-Host '[qdrant] 复用已有容器 qdrant（数据卷 qdrant_storage 保留）' -ForegroundColor Green
        return
    }
    if (-not (Test-HostPortFree 6333)) {
        Write-Host '[qdrant] 6333 已被占用：跳过创建。' -ForegroundColor Yellow
        return
    }
    Write-Host '[qdrant] 创建独立容器 qdrant ...' -ForegroundColor Yellow
    docker run -d --name qdrant --network $Net `
        -v qdrant_storage:/qdrant/storage `
        -p 6333:6333 -p 6334:6334 `
        --restart unless-stopped qdrant/qdrant:v1.13.0 | Out-Null
}

# ---------- MySQL（仅供本机其他项目复用；本项目使用 PostgreSQL） ----------
function Ensure-Mysql {
    if (Test-ContainerExists 'mysql') {
        if (-not (Test-IsTaot 'mysql')) {
            Write-Host '[mysql] 存在外部同名容器 mysql，跳过创建（请自行管理连接）。' -ForegroundColor Yellow
            return
        }
        Start-IfStopped 'mysql'
        Ensure-NetConnect 'mysql'
        Write-Host '[mysql] 复用已有容器 mysql' -ForegroundColor Green
        return
    }
    if (-not (Test-HostPortFree 3306)) {
        Write-Host '[mysql] 3306 已被本机 MySQL/其它服务占用：跳过创建。' -ForegroundColor Yellow
        Write-Host '          如需释放：以【管理员】运行以下命令后重试本脚本：' -ForegroundColor Gray
        Write-Host '            Stop-Service MySQL84; Set-Service MySQL84 -StartupType Disabled' -ForegroundColor White
        return
    }
    Write-Host '[mysql] 创建独立容器 mysql（root/root@123, 数据卷 taot_mysql_data）...' -ForegroundColor Yellow
    docker run -d --name mysql --network $Net `
        --label com.taot.infra=true `
        -v "${MysqlDataVol}:/var/lib/mysql" `
        -p 3306:3306 `
        -e MYSQL_ROOT_PASSWORD='root@123' `
        --restart unless-stopped mysql:8 | Out-Null
}

# ---------- 主流程 ----------
Ensure-Network

if ($OnlyMysql) {
    Ensure-Mysql
} else {
    Ensure-Postgres
    Ensure-Redis
    Ensure-Qdrant
    Ensure-Mysql
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  基础服务检查完成。下一步：' -ForegroundColor Green
Write-Host '  docker compose up -d --build backend worker beat' -ForegroundColor White
Write-Host '============================================' -ForegroundColor Cyan
