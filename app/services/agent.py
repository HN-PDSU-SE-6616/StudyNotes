"""AI Agent：会话上下文 + 相似问题热缓存 + 工具调用循环

- 会话：按 (user_id, session_id) 在 Redis 存最近对话（上限 24 条，TTL 6h），
  可整体清空（assistant/context/clear）。
- 热缓存：把「问题→答案」按用户缓存（上限 100 条，TTL 24h）；精确或高相似
  （字符 bigram Dice ≥0.88 且长度 ≥6）重复/相似问题直接复用，减少 LLM 调用。
- 工具：接入 app.services.tools.REGISTRY 的 function calling 循环（≤4 轮），
  模型不支持 tools 时自动降级为普通对话。

Redis 不可用时全部优雅降级（无会话/无缓存，仅影响记忆与提速）。
"""
import json
import logging
import re
import time
from typing import Any, Optional

from app.core.config import settings
from app.services import tools

logger = logging.getLogger(__name__)

CTX_TTL = 6 * 3600
CACHE_TTL = 24 * 3600
MAX_HISTORY = 24        # 会话最多保留消息条数
MAX_CACHE = 100         # 每用户缓存问题数（超出淘汰最旧）
MAX_TOOL_ROUNDS = 4     # 单次对话最多工具轮次
CACHE_SIM_THRESHOLD = 0.88

_redis: Any = None


def _get_redis():
    global _redis
    if _redis is None:
        from redis import asyncio as aioredis
        _redis = aioredis.from_url(
            settings.redis_url, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
    return _redis


# ---------- 问题归一化 / 相似度 ----------
_NORM_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _norm(q: str) -> str:
    return _NORM_RE.sub("", (q or "").lower()).strip()


def _dice(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) < 2 or len(b) < 2:
        return 1.0 if a == b else 0.0
    def grams(s: str) -> set:
        return {s[i:i + 2] for i in range(len(s) - 1)}
    ga, gb = grams(a), grams(b)
    inter = len(ga & gb)
    return (2.0 * inter) / (len(ga) + len(gb))


def _lcs_ratio(a: str, b: str) -> float:
    """最长公共子序列长度 / 较长串长度（对短句同义改写更稳健）"""
    n, m = len(a), len(b)
    if not n or not m:
        return 0.0
    prev = [0] * (m + 1)
    for i in range(n):
        cur = [0] * (m + 1)
        for j in range(m):
            if a[i] == b[j]:
                cur[j + 1] = prev[j] + 1
            else:
                cur[j + 1] = max(prev[j + 1], cur[j])
        prev = cur
    return prev[m] / max(n, m)


def _is_similar(a: str, b: str) -> bool:
    """重复/近似问题判定：归一化后相同 或 高相似（dice/LCS 任一达标）"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if min(len(na), len(nb)) < 6:
        return False  # 短问题只接受完全一致，避免误命中
    return _dice(na, nb) >= 0.74 or _lcs_ratio(na, nb) >= 0.72


# ---------- 热缓存 ----------
async def cache_get(uid: str, question: str) -> Optional[str]:
    try:
        raw = await _get_redis().get(f"taot:asst:cache:{uid}")
        if not raw:
            return None
        items = json.loads(raw) or []
        for it in items:
            if _is_similar(it.get("q", ""), question):
                it["ts"] = time.time()
                await _get_redis().setex(
                    f"taot:asst:cache:{uid}", CACHE_TTL, json.dumps(items, ensure_ascii=False))
                return it.get("a") or None
    except Exception:  # noqa: BLE001 Redis 不可用 → 直接 miss
        logger.debug("cache_get 不可用，按 miss 处理")
    return None


async def cache_put(uid: str, question: str, answer: str) -> None:
    try:
        key = f"taot:asst:cache:{uid}"
        raw = await _get_redis().get(key)
        items = json.loads(raw) if raw else []
        items = [it for it in items if not _is_similar(it.get("q", ""), question)]
        items.append({"q": question, "a": answer, "ts": time.time()})
        items = items[-MAX_CACHE:]
        await _get_redis().setex(key, CACHE_TTL, json.dumps(items, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        logger.debug("cache_put 不可用，跳过")


# ---------- 会话上下文 ----------
def _ctx_key(uid: str, session_id: str) -> str:
    return f"taot:asst:ctx:{uid}:{session_id}"


async def history_get(uid: str, session_id: str) -> list[dict]:
    try:
        raw = await _get_redis().get(_ctx_key(uid, session_id))
        if raw:
            items = json.loads(raw) or []
            return [m for m in items if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    except Exception:  # noqa: BLE001
        logger.debug("history_get 不可用，返回空")
    return []


async def history_append(uid: str, session_id: str, question: str, answer: str) -> None:
    try:
        items = await history_get(uid, session_id)
        items.append({"role": "user", "content": question})
        if answer:
            items.append({"role": "assistant", "content": answer})
        if len(items) > MAX_HISTORY:
            items = items[-MAX_HISTORY:]
        await _get_redis().setex(_ctx_key(uid, session_id), CTX_TTL,
                                 json.dumps(items, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        logger.debug("history_append 不可用，跳过")


async def history_clear(uid: str, session_id: str) -> None:
    try:
        await _get_redis().delete(_ctx_key(uid, session_id))
    except Exception:  # noqa: BLE001
        logger.debug("history_clear 不可用，跳过")


# ---------- Agent 主循环 ----------
def run_agent(
    messages: list[dict],
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    tools_enabled: bool = True,
    client_context: Optional[dict] = None,
) -> tuple[str, str, bool]:
    """执行带工具循环的对话，返回 (reply, model, used_tools)。

    工具开启时优先调用 OpenAI 兼容 function calling；若服务端不支持 tools，
    自动去掉 tools 重试一次（模型不支持不会阻断对话）。
    """
    from openai import OpenAI

    cfg_base = base_url or settings.llm_base_url
    cfg_key = api_key or settings.llm_api_key
    cfg_model = model or settings.llm_model
    if not cfg_key:
        raise RuntimeError("未配置 LLM API Key：请在 .env 配置 LLM_API_KEY（模型配置统一由 .env 管理）")

    client = OpenAI(api_key=cfg_key, base_url=cfg_base or None, timeout=120.0)
    use_tools = tools_enabled
    used_tools = False
    rounds = 0

    while True:
        working = [dict(m) for m in messages]
        if use_tools:
            note = ("你可以调用工具获取实时/外部数据，可用工具：" +
                    "、".join(t.name for t in tools.REGISTRY.values()) +
                    "。需要实时信息时先调用工具，基于工具结果回答，不要编造。")
            if client_context:
                note += f"；用户浏览器端信息：{json.dumps(client_context, ensure_ascii=False)}"
            working = [{"role": "system", "content": note}] + working

        kwargs: dict[str, Any] = {
            "model": cfg_model,
            "messages": working,  # type: ignore[arg-type]
            "temperature": temperature,
        }
        if use_tools:
            kwargs["tools"] = tools.list_tools()

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if use_tools:
                logger.info("模型不支持 tools，降级为普通对话: %s: %s",
                            type(exc).__name__, exc)
                use_tools = False
                continue  # 去掉 tools 与系统工具提示重试一次
            raise

        message = resp.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if use_tools and tool_calls:
            rounds += 1
            used_tools = True
            if rounds > MAX_TOOL_ROUNDS:
                raise RuntimeError(f"工具调用超过 {MAX_TOOL_ROUNDS} 轮仍未结束，已中止。")
            asst_msg: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
            asst_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name,
                                 "arguments": tc.function.arguments or "{}"},
                }
                for tc in tool_calls
            ]
            messages.append(asst_msg)
            ctx: dict[str, Any] = {"client_context": client_context or {}}
            for tc in tool_calls:
                result = tools.execute_tool(tc.function.name, tc.function.arguments, ctx)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue
        return (message.content or ""), cfg_model, used_tools
