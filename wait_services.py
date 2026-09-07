"""容器启动依赖等待：轮询基础服务端口就绪后退出 0。

用法: python wait_services.py [host:port ...]
默认等待: postgres:5432 redis:6379 qdrant:6333
"""
import socket
import sys
import time

DEFAULT_TARGETS = [
    ("postgres", 5432),
    ("redis", 6379),
    ("qdrant", 6333),
]
RETRIES = 40  # 每 2s 一次，最长约 80s


def _parse_targets(args):
    if not args:
        return DEFAULT_TARGETS
    targets = []
    for item in args:
        host, _, port = item.partition(":")
        targets.append((host, int(port)))
    return targets


def wait(targets):
    deadline = time.time() + RETRIES * 2
    pending = list(targets)
    print(f"[wait_services] 等待 {len(pending)} 个基础服务就绪...", flush=True)
    while pending and time.time() < deadline:
        for t in list(pending):
            host, port = t
            try:
                with socket.create_connection((host, port), timeout=2):
                    pending.remove(t)
                    print(f"[wait_services] OK {host}:{port}", flush=True)
            except OSError:
                pass
        if pending:
            time.sleep(2)
    if pending:
        missing = ", ".join(f"{h}:{p}" for h, p in pending)
        print(f"[wait_services] 超时仍未就绪: {missing}", flush=True)
        sys.exit(1)
    print("[wait_services] 全部就绪", flush=True)


if __name__ == "__main__":
    wait(_parse_targets(sys.argv[1:]))
