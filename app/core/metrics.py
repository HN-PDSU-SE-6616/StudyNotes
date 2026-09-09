"""Prometheus 指标（APM 观测数据面）

- HTTP：请求计数（method/route/status）、耗时直方图、并发在途（in-flight）；
- Agent：工具调用计数（tool/ok），用于观测 AI 助手工具命中率与失败率；
- 使用独立 CollectorRegistry（不绑定默认系统收集器，避免 Windows 上部分
  系统指标不可用导致 scrape 报错），`/metrics` 由 app/main.py 注册并暴露。

面板：deploy/monitoring 提供 Prometheus + Grafana 一键编排与预置仪表盘。
"""
from __future__ import annotations

import time

from fastapi import Request, Response
from prometheus_client import (  # type: ignore[import-untyped]
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

_registry = CollectorRegistry(auto_describe=False)

REQUEST_TOTAL = Counter(
    "taot_http_requests_total",
    "HTTP 请求总数（按 方法/路由模板/状态码 分桶）",
    ["method", "route", "status"],
    registry=_registry,
)
REQUEST_DURATION = Histogram(
    "taot_http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_registry,
)
IN_FLIGHT = Gauge(
    "taot_http_inflight_requests",
    "当前处理中的 HTTP 请求数",
    ["method"],
    registry=_registry,
)
TOOL_CALLS_TOTAL = Counter(
    "taot_agent_tool_calls_total",
    "Agent 工具调用次数（按 工具名/是否成功）",
    ["tool", "ok"],
    registry=_registry,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """统计每个 HTTP 请求（跳过 /metrics 自身，避免抓取自增噪音）"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)

        route = getattr(request.scope.get("route"), "path", None)
        label_route = route if isinstance(route, str) and route.startswith("/") else path
        method = request.method or "GET"
        start = time.perf_counter()
        IN_FLIGHT.labels(method).inc()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            IN_FLIGHT.labels(method).dec()
            status = str(getattr(response, "status_code", 500))
            REQUEST_TOTAL.labels(method=method, route=label_route, status=status).inc()
            REQUEST_DURATION.labels(method=method, route=label_route) \
                .observe(max(0.0, time.perf_counter() - start))


def record_tool_call(tool: str, ok: bool) -> None:
    """Agent 工具执行结果计数（tools.execute_tool 调用）"""
    TOOL_CALLS_TOTAL.labels(tool=tool or "unknown", ok="true" if ok else "false").inc()


def metrics_http() -> Response:
    """GET /metrics：以 Prometheus 文本协议输出当前指标"""
    return Response(generate_latest(_registry), media_type=CONTENT_TYPE_LATEST)
