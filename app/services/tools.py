"""AI Agent 工具函数注册表（可扩展）

每个工具 = ToolDef{name, description, parameters(JSON Schema), handler(ctx, **args)}。
新增工具只需：写一个 handler + 在 REGISTRY 注册一条，前端/对话无需改动。

内置工具（运行在服务端容器内，实时数据走公网免费接口）：
- get_weather      实时天气（open-meteo，无 key）
- get_ip           外网/内网 IP
- get_system_info  服务端与客户端系统参数（CPU/GPU/内存/浏览器）
- fetch_web_page   httpx 抓取简单网页 → BeautifulSoup4 提取正文文本
- web_search       DuckDuckGo html 端网页搜索（标题/链接/摘要）
- web_research     联网研究工作流：拆词→多源搜索→抓正文→要点汇总
- search_knowledge_base  知识库（笔记）向量检索（需登录 + Embedding 配置）
"""
import json
import logging
import platform
import re
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

from app.core.metrics import record_tool_call

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, dict], str]  # handler(ctx, **args) -> str


REGISTRY: dict[str, ToolDef] = {}


def register_tool(name: str, description: str, parameters: dict):
    """注册工具（装饰器），参数为 OpenAI function calling 的 JSON Schema parameters"""
    def deco(fn):
        REGISTRY[name] = ToolDef(
            name=name, description=description, parameters=parameters,
            handler=fn,
        )
        return fn
    return deco


# ---------- 可测试的网络出口（monkeypatch 点） ----------
def _http_get(url: str, params: Optional[dict] = None, timeout: float = 10.0) -> httpx.Response:
    return httpx.get(url, params=params, timeout=timeout, headers={"User-Agent": _UA})


# ---------- 1. 实时天气 ----------
_WMO = {
    0: "晴", 1: "大部晴朗", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇", 51: "毛毛雨", 53: "小毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "中阵雨", 82: "强阵雨", 85: "小阵雪", 86: "大阵雪",
    95: "雷阵雨", 96: "雷阵雨伴小冰雹", 99: "雷阵雨伴大冰雹",
}


@register_tool(
    "get_weather",
    "查询指定城市的实时天气与当日气温（用户问天气/气温/会不会下雨时调用）",
    {"type": "object",
     "properties": {"city": {"type": "string", "description": "城市名，如：北京 / 上海 / London"}},
     "required": ["city"]},
)
def _weather(ctx: dict, city: str = "") -> str:
    city = (city or "").strip()
    if not city:
        return "缺少参数 city（城市名），请让用户明确城市后重试。"
    try:
        geo = _http_get("https://geocoding-api.open-meteo.com/v1/search",
                        {"name": city, "count": 1, "language": "zh", "format": "json"}).json()
        results = geo.get("results") or []
        if not results:
            return f"未找到城市「{city}」，请核对城市名。"
        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        name = loc.get("name", city)
        region = loc.get("admin1", "") or loc.get("country", "")
        f = _http_get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon,
            "current": ["temperature_2m", "relative_humidity_2m",
                        "weather_code", "wind_speed_10m", "is_day"],
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "forecast_days": 1, "timezone": "auto",
        }).json()
        cur = f.get("current", {})
        code = int(cur.get("weather_code", 0))
        text = _WMO.get(code, f"码{code}")
        high = (f.get("daily", {}).get("temperature_2m_max") or [None])[0]
        low = (f.get("daily", {}).get("temperature_2m_min") or [None])[0]
        parts = [f"{name}（{region}）当前天气：{text}"]
        if cur.get("temperature_2m") is not None:
            parts.append(f"气温 {cur['temperature_2m']}℃")
        if low is not None and high is not None:
            parts.append(f"今日 {low}~{high}℃")
        if cur.get("relative_humidity_2m") is not None:
            parts.append(f"湿度 {cur['relative_humidity_2m']}%")
        if cur.get("wind_speed_10m") is not None:
            parts.append(f"风速 {cur['wind_speed_10m']}km/h")
        return "，".join(parts) + "。"
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_weather 失败: %s", exc)
        return f"天气服务暂时不可用（{type(exc).__name__}），请稍后再试。"


# ---------- 2. IP ----------
@register_tool(
    "get_ip",
    "获取本机/服务器当前的公网 IP 与内网 IP（用户问我的 IP、公网地址时调用）",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
def _ip(ctx: dict) -> str:
    try:
        data = _http_get("https://api.ipify.org", {"format": "json"}).json()
        public = data.get("ip", "")
    except Exception:  # noqa: BLE001
        public = ""
    try:
        local = socket.gethostbyname(socket.gethostname())
    except Exception:  # noqa: BLE001
        local = ""
    out = []
    if public:
        out.append(f"公网 IP：{public}")
    if local:
        out.append(f"内网 IP：{local}")
    return "；".join(out) if out else "无法获取 IP（网络受限）。"


# ---------- 3. 系统参数 ----------
@register_tool(
    "get_system_info",
    "获取服务器或用户客户端(浏览器)的系统参数：CPU/GPU/内存/操作系统/浏览器等",
    {"type": "object",
     "properties": {"scope": {
         "type": "string", "enum": ["all", "server", "client"],
         "description": "all=服务端+客户端；server=仅部署环境；client=仅用户浏览器端"}},
     "required": []},
)
def _system(ctx: dict, scope: str = "all") -> str:
    lines: list[str] = []
    if scope in ("all", "server"):
        gpu = ""
        try:
            out = subprocess.run(  # noqa: S603
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=2,
                check=False,
            ).stdout.strip()
            if out:
                gpu = out.splitlines()[0]
        except Exception:  # noqa: BLE001
            gpu = ""
        cpu = f"{platform.machine()} / {_cpu_count()} 核"
        lines.append("服务器：系统=" + platform.system() + platform.release() +
                     f"，{cpu}" +
                     f"，Python {platform.python_version()}" +
                     (f"，GPU={gpu}" if gpu else "，GPU=未检测到 NVIDIA 独显"))
    if scope in ("all", "client"):
        cc = ctx.get("client_context") or {}
        if cc:
            keys = {
                "os": "操作系统", "browser": "浏览器", "platform": "平台",
                "cores": "CPU 逻辑核", "memory": "内存(GB)", "gpu": "GPU 渲染器",
                "lang": "语言", "screen": "屏幕",
            }
            detail = "，".join(f"{keys.get(k, k)}={v}" for k, v in cc.items() if v)
            lines.append(f"客户端(浏览器)：{detail or '未采集到参数'}")
        else:
            lines.append("客户端信息：未采集（浏览器环境未上报）")
    return "。".join(lines) + "。" if lines else "暂无可用系统信息。"


def _cpu_count() -> str:
    try:
        import os
        return str(os.cpu_count() or 1)
    except Exception:  # noqa: BLE001
        return "1"


# ---------- 4. 抓取网页正文 ----------
@register_tool(
    "fetch_web_page",
    "抓取指定网页的正文纯文本（先移除脚本/样式/导航等噪音），用于回答网页内容相关问题",
    {"type": "object",
     "properties": {
         "url": {"type": "string", "description": "完整 http(s) 网址"},
         "limit": {"type": "integer", "description": "返回最大字符数，默认 3000"}},
     "required": ["url"]},
)
def _fetch(ctx: dict, url: str = "", limit: int = 3000) -> str:
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        return "参数 url 必须是 http(s) 开头的完整网址。"
    try:
        resp = _http_get(url, timeout=12.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return f"网页抓取失败（{type(exc).__name__}: {exc}）。"
    return _html_to_text(resp.text, url=url, limit=int(limit or 3000))


def _html_to_text(html: str, url: str = "", limit: int = 3000) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "服务端缺少 BeautifulSoup4 依赖，无法解析网页。"
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe",
                     "nav", "footer", "form", "aside", "button"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    body = soup.get_text("\n")
    body = re.sub(r"[ \t\xa0]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n", body).strip()
    out = (f"标题：{title}\n" if title else "") + (f"来源：{url}\n" if url else "") + body
    return out[:limit]


# ---------- 5. 网页搜索 ----------
def _ddg_results(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo html 端搜索，返回 [{title,url,snippet}]（供 search/web_research 复用）"""
    resp = _http_get("https://html.duckduckgo.com/html/", {"q": query, "kl": "cn-zh"})
    resp.raise_for_status()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict] = []
    for result in soup.select(".result")[: min(int(max_results or 5), 8)]:
        a = result.select_one("a.result__a")
        snip = result.select_one(".result__snippet")
        if not a:
            continue
        href = a.get("href", "")
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            from urllib.parse import unquote
            href = unquote(m.group(1))
        items.append({
            "title": a.get_text(strip=True),
            "url": href,
            "snippet": snip.get_text(" ", strip=True) if snip else "",
        })
    return items


@register_tool(
    "web_search",
    "联网搜索网页，返回标题/链接/摘要列表（用 fetch_web_page 可进一步抓取正文）",
    {"type": "object",
     "properties": {
         "query": {"type": "string", "description": "搜索关键词"},
         "max_results": {"type": "integer", "description": "返回条数，默认 5，最大 8"}},
     "required": ["query"]},
)
def _search(ctx: dict, query: str = "", max_results: int = 5) -> str:
    query = (query or "").strip()
    if not query:
        return "缺少参数 query。"
    try:
        items = _ddg_results(query, max_results)
        if not items:
            return "未搜索到结果，可换个关键词或直接提供 URL 用 fetch_web_page。"
        return json.dumps(items, ensure_ascii=False)[:4000]
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_search 失败: %s", exc)
        return f"搜索服务暂时不可用（{type(exc).__name__}）。"


# ---------- 6. 联网研究工作流（关键词→搜索→抓取→要点） ----------
@register_tool(
    "web_research",
    "联网研究工作流：自动把问题拆成检索词→搜索多个来源→抓取相关文档正文→"
    "汇总各来源要点与链接。适合需要联网取证/对比/了解最新现状/查官方文档等场景，"
    "一个工具调用即可完成多步检索，避免多次来回。",
    {"type": "object",
     "properties": {
         "question": {"type": "string", "description": "要调研的问题/主题，如：Python 3.13 新特性"},
         "max_results": {"type": "integer", "description": "每轮搜索条数，默认 5，最大 8"},
         "max_sources": {"type": "integer", "description": "最终抓取正文的来源数，默认 3，最大 5"},
         "per_source_chars": {"type": "integer", "description": "每个来源保留正文字符数，默认 1800，最大 3000"}},
     "required": ["question"]},
)
def _web_research(ctx: dict, question: str = "", max_results: int = 5,
                  max_sources: int = 3, per_source_chars: int = 1800) -> str:
    """拆词→多源搜索→相关度排序→抓正文→要点汇总（无需二次 LLM）"""
    question = (question or "").strip()
    if not question:
        return "缺少参数 question。"
    try:
        # 1) 检索词：主问题 + “对比/和/与”切出的子主题（去重，最多 3 组）
        queries = [question]
        for seg in re.split(r"[和与及、vs\.]|对比|比较", question):
            seg = seg.strip(" ?？，,")
            if 4 <= len(seg) <= 60 and seg and seg not in queries:
                queries.append(seg)
            if len(queries) >= 3:
                break
        # 2) 各检索词搜索并去重合并
        items: list[dict] = []
        seen: set[str] = set()
        for q in queries:
            for it in _ddg_results(q, max_results=int(max_results or 5)):
                url = it.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    items.append(it)
        if not items:
            return "联网搜索未找到相关结果，请换一种问法或直接提供 URL 用 fetch_web_page。"
        # 3) 相关度粗排：标题/摘要命中问题关键词多的优先
        terms = [t for t in re.split(r"\W+", question.lower()) if len(t) >= 2]
        def _score(it: dict) -> int:
            blob = f"{it.get('title', '')} {it.get('snippet', '')}".lower()
            return sum(1 for t in terms if t in blob)
        items.sort(key=lambda it: (_score(it), len(it.get("title", ""))), reverse=True)
        items = items[: min(int(max_sources or 3), 5)]
        # 4) 逐条抓取正文并截断
        parts: list[str] = []
        for i, it in enumerate(items, start=1):
            title = it.get("title", "") or it.get("url", "")
            body = ""
            url = it.get("url", "")
            if re.match(r"^https?://", url, re.I):
                try:
                    resp = _http_get(url, timeout=12.0)
                    resp.raise_for_status()
                    body = _html_to_text(resp.text, url=url,
                                         limit=int(per_source_chars or 1800))
                except Exception as exc:  # noqa: BLE001
                    body = f"（抓取失败：{type(exc).__name__}）"
            parts.append(
                f"[{i}] {title}\n    链接：{url}\n    摘要：{it.get('snippet', '') or '无'}\n"
                f"    正文要点：{body[: int(per_source_chars or 1800)]}"
            )
        return "\n\n".join(parts)[:6000]
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_research 失败: %s", exc)
        return f"联网研究工作流暂时不可用（{type(exc).__name__}）。"


# ---------- 对外接口 ----------
def list_tools() -> list[dict]:
    """转换为 OpenAI function calling tools 数组"""
    return [{
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        },
    } for t in REGISTRY.values()]


def execute_tool(name: str, arguments: dict, ctx: Optional[dict] = None) -> str:
    """执行工具并返回给 LLM 的字符串结果（异常安全，错误也以文本返回）"""
    tool = REGISTRY.get(name)
    if tool is None:
        record_tool_call(name, False)
        return f"未知工具：{name}。可用工具：{', '.join(REGISTRY)}"
    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")
        if not isinstance(arguments, dict):
            arguments = {}
        result = str(tool.handler(ctx or {}, **arguments))[:4000]
        record_tool_call(name, True)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("工具 %s 执行失败: %s", name, exc, exc_info=True)
        record_tool_call(name, False)
        return f"工具 {name} 执行出错：{type(exc).__name__}: {exc}"


# ---------- 6. 知识库 RAG 检索 ----------
@register_tool(
    "search_knowledge_base",
    "在用户的知识库（笔记）中做向量检索并返回相关内容片段。"
    "当问题涉及‘我的笔记/知识库/我学过的…/项目里的内容’等当前知识库内容时，"
    "必须先调用本工具检索到原文后再基于检索结果回答；不要凭空作答。",
    {"type": "object",
     "properties": {
         "question": {"type": "string", "description": "要检索的问题/关键词"},
         "project_id": {"type": "string", "description": "限定单个项目（可选，留空检索全部可访问项目）"},
         "top_k": {"type": "integer", "description": "返回片段数，默认 3，最大 8"}},
     "required": ["question"]},
)
def _kb_search(ctx: dict, question: str = "", project_id: str = "", top_k: int = 3) -> str:
    """知识库检索：工具上下文需由路由注入 kb（可访问项目 + 当前项目）"""
    question = (question or "").strip()
    if not question:
        return "缺少参数 question（检索关键词），请让用户明确后再试。"
    kb = ctx.get("kb") or {}
    ids = kb.get("accessible_project_ids") or []
    if not kb.get("enabled") or not ids:
        return "知识库检索暂不可用：当前未登录，或没有任何可访问的知识库项目。"
    pid = (project_id or "").strip() or kb.get("project_id") or None
    if pid and pid not in ids:
        return "你无权访问该项目的内容，无法检索。"
    scope: list = ids if not pid else [pid]
    try:
        from app.services import rag as rag_svc
        res = rag_svc.search_only(question, scope, top_k=min(max(int(top_k or 3), 1), 8))
    except RuntimeError as exc:
        return f"知识库检索不可用：{exc}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("search_knowledge_base 失败: %s", exc, exc_info=True)
        return f"知识库检索失败：{type(exc).__name__}: {exc}"
    if not res.get("found"):
        return "知识库中未找到与问题相关的内容，可如实告知用户知识库内没有该资料。"
    parts = [f"知识库检索命中 {len(res['sources'])} 条（请基于以下原文回答并标注来源编号）："]
    for s in res["sources"]:
        head = f"【{s['title']}】"
        if s.get("heading_path"):
            head += f"（{s['heading_path']}）"
        parts.append(f"{head}：{(s.get('content') or '')[:1200]}")
    return "\n\n".join(parts)[:3800] + ("\n（内容较长已截断）" if len(parts) > 0 else "")
