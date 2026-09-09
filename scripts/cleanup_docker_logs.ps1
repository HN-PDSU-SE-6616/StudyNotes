# ============================================================
#   Taot 知识库 — Docker json-file 日志时间维度清理（可选，不自动注册）
#
#   背景：Docker 原生轮换（json-file max-size/max-file）只按“体积”，
#         不支持按“天数”。本脚本借助临时 python 容器解析各容器
#         `-json.log`（每行带 time 字段），把超过 -Days 天的日志条目
#         截掉，实现近似“3 天保留期”。
#
#   用法：
#     powershell -ExecutionPolicy Bypass -File scripts/cleanup_docker_logs.ps1          # 默认 3 天
#     powershell -ExecutionPolicy Bypass -File scripts/cleanup_docker_logs.ps1 -Days 3 -MinSizeMB 50
#     powershell -ExecutionPolicy Bypass -File scripts/cleanup_docker_logs.ps1 -DryRun # 只预览不执行
#
#   可选每日计划任务（注册示例，不会自动执行）：
#     schtasks /Create /TN "Taot-CleanupDockerLogs" /TR "powershell -ExecutionPolicy Bypass -File D:\PythonProject\NoteLog\scripts\cleanup_docker_logs.ps1 -Days 3" /SC DAILY /ST 04:00 /F
#
#   注意：需要截断的容器会先 stop → 改写 json.log → start（短暂停机，
#         仅当日志内确有超期条目且体积 ≥ MinSizeMB 时才发生，日常为空转）。
# ============================================================

param(
    [int]$Days = 3,
    [int]$MinSizeMB = 20,
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$Targets = @('taot-backend', 'taot-worker', 'taot-beat', 'postgres', 'redis', 'qdrant', 'mysql')

# 临时 python 脚本：读/写 Docker 容器 json.log（挂载进辅助容器执行）
$PyPath = Join-Path $env:TEMP 'taot_trim_docker_log.py'
@'
import json, sys
from datetime import datetime, timedelta, timezone

def parse_time(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def main():
    path = sys.argv[1]
    mode = sys.argv[2]                      # check | rewrite
    days = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    old = 0
    kept_lines = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            total += 1
            ts = None
            try:
                ts = parse_time((json.loads(line).get("time") or ""))
            except Exception:
                pass
            if ts is None or ts >= cutoff:
                kept_lines.append(line)
            else:
                old += 1
    if mode == "check":
        size = len(open(path, "rb").read())
        print(f"{size} {old}")
        return
    # rewrite：仅保留超期条目被截断后的内容
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(kept_lines))
        if kept_lines:
            f.write("\n")
    print(f"kept={len(kept_lines)} trimmed={old}")

if __name__ == "__main__":
    main()
'@ | Set-Content -Path $PyPath -Encoding UTF8

function Test-DockerAvailable {
    try {
        docker version --format '{{.Server.Version}}' 2>$null | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Invoke-TruncateLog([string]$name) {
    if (-not (Test-DockerAvailable)) {
        Write-Host "[$name] Docker 不可用，跳过。" -ForegroundColor Yellow
        return
    }
    $running = (docker inspect -f '{{.State.Running}}' $name 2>$null | Out-String).Trim()
    if ($running -ne 'true') {
        Write-Host "[$name] 未运行，跳过。" -ForegroundColor DarkGray
        return
    }
    $logPath = (docker inspect -f '{{.LogPath}}' $name 2>$null | Out-String).Trim()
    if (-not $logPath -or $logPath -notlike '*json.log') {
        Write-Host "[$name] 未使用 json-file 驱动或无日志文件，跳过。" -ForegroundColor DarkGray
        return
    }
    $logDir = Split-Path -Parent $logPath
    $logFile = Split-Path -Leaf $logPath
    if (-not $logDir -or -not $logFile) { return }

    # 只读检查：输出 "<sizeBytes> <oldEntries>"
    $check = (docker run --rm -v "${logDir}:/logs:ro" -v "${PyPath}:/trim.py:ro" `
        python:3.12-alpine python /trim.py "/logs/$logFile" check $Days 2>$null | Out-String).Trim()
    $parts = $check -split ' '
    if ($parts.Count -lt 2) {
        Write-Host "[$name] 无法读取日志（$check），跳过。" -ForegroundColor Yellow
        return
    }
    $sizeBytes = 0L; $oldEntries = 0
    [long]::TryParse($parts[0], [ref]$sizeBytes) | Out-Null
    [int]::TryParse($parts[1], [ref]$oldEntries) | Out-Null

    if ($oldEntries -le 0) {
        Write-Host "[$name] 最近 $Days 天内无超期日志，无需清理。" -ForegroundColor Green
        return
    }
    if ($sizeBytes -lt ($MinSizeMB * 1MB)) {
        Write-Host "[$name] 日志 ${sizeBytes}B 小于阈值 ${MinSizeMB}MB，跳过（避免无谓重启）。" -ForegroundColor DarkGray
        return
    }

    $cutMB = [math]::Round($sizeBytes / 1MB, 1)
    if ($DryRun) {
        Write-Host "[$name] [DryRun] 将清理 $oldEntries 条超期日志（当前 ${cutMB}MB）→ 需重启容器。" -ForegroundColor Cyan
        return
    }
    Write-Host "[$name] 清理 $oldEntries 条超期日志（当前 ${cutMB}MB）：stop → 截断 → start ..." -ForegroundColor Yellow
    try {
        docker stop $name 2>$null | Out-Null
        $out = (docker run --rm -v "${logDir}:/logs" -v "${PyPath}:/trim.py:ro" `
            python:3.12-alpine python /trim.py "/logs/$logFile" rewrite $Days 2>$null | Out-String).Trim()
        Write-Host "[$name] $out" -ForegroundColor Green
    } finally {
        docker start $name 2>$null | Out-Null
    }
}

Write-Host '============================================' -ForegroundColor Cyan
Write-Host "  Docker 日志时间维度清理（保留 $Days 天）" -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan

foreach ($name in $Targets) {
    Invoke-TruncateLog $name
}

Remove-Item $PyPath -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '完成。基础轮换仍由 infra.ps1 / docker-compose 的 max-size=20m/max-file=3 兜底。' -ForegroundColor Green
