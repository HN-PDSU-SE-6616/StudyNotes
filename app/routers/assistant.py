"""AI 助手通用对话代理（OpenAI 兼容 /chat/completions）

用于前端“悬浮 AI 助手”的自由对话：请求体可携带 base_url/model/api_key 覆盖
后端默认配置（前端可把配置存在浏览器本地做个性化），未携带时回落 .env 的
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。密钥不落库、不打日志。

- POST /assistant/chat          整段返回
- POST /assistant/chat/stream   SSE 流式（data: {json} 行，末尾 data: [DONE]）
"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import SQLModel

from app.core.config import settings

router = APIRouter(prefix="/assistant", tags=["AI 助手"])


class ChatMessage(SQLModel):
    role: str  # system / user / assistant
    content: str


class ChatRequest(SQLModel):
    messages: list[ChatMessage]
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    system: Optional[str] = None


class ChatResponse(SQLModel):
    reply: str
    model: str


def _resolve_config(base_url, api_key, model):
    cfg_base = base_url or settings.llm_base_url
    cfg_key = api_key or settings.llm_api_key
    cfg_model = model or settings.llm_model
    if not cfg_key:
        raise RuntimeError("未配置 LLM API Key：请在悬浮助手设置中填写，或在 .env 配置 LLM_API_KEY")
    return cfg_base, cfg_key, cfg_model


def llm_chat(
    messages: list[dict],
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> tuple[str, str]:
    """同步调用 OpenAI 兼容 chat completions，返回 (reply, model)"""
    from openai import OpenAI

    cfg_base, cfg_key, cfg_model = _resolve_config(base_url, api_key, model)
    client = OpenAI(api_key=cfg_key, base_url=cfg_base or None, timeout=120.0)
    resp = client.chat.completions.create(
        model=cfg_model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
    )
    try:
        reply = resp.choices[0].message.content or ""
    except Exception:  # noqa: BLE001
        reply = ""
    return reply, cfg_model


def llm_chat_stream(
    messages: list[dict],
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
):
    """流式调用 OpenAI 兼容 chat completions；逐段 yield 文本增量（generator）。"""
    from openai import OpenAI

    cfg_base, cfg_key, cfg_model = _resolve_config(base_url, api_key, model)
    client = OpenAI(api_key=cfg_key, base_url=cfg_base or None, timeout=120.0)
    stream = client.chat.completions.create(
        model=cfg_model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content
        except Exception:  # noqa: BLE001
            delta = None
        if delta:
            yield delta


def _sse_generator(payload: dict, messages: list[dict]):
    """把 llm_chat_stream 的输出包装为 SSE data 行；错误以事件下发，不中断连接"""
    try:
        for delta in llm_chat_stream(
            messages,
            base_url=payload.get("base_url"),
            api_key=payload.get("api_key"),
            model=payload.get("model"),
            temperature=payload.get("temperature", 0.7),
        ):
            yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
    except RuntimeError as exc:
        yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
    except Exception as exc:  # noqa: BLE001
        yield f"data: {json.dumps({'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat", response_model=ChatResponse, summary="通用对话（OpenAI 兼容）")
async def chat(body: ChatRequest):
    if not body.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")
    msgs: list[dict] = []
    if body.system:
        msgs.append({"role": "system", "content": body.system})
    for m in body.messages:
        if m.content and m.content.strip():
            msgs.append({"role": m.role, "content": m.content})
    if not msgs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息内容为空")
    try:
        reply, model = llm_chat(
            msgs,
            base_url=body.base_url,
            api_key=body.api_key,
            model=body.model,
            temperature=body.temperature,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 调用失败: {type(exc).__name__}: {exc}",
        )
    return ChatResponse(reply=reply, model=model)


@router.post("/chat/stream", summary="通用对话流式（SSE / text/event-stream）")
async def chat_stream(body: ChatRequest):
    if not body.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")
    msgs: list[dict] = []
    if body.system:
        msgs.append({"role": "system", "content": body.system})
    for m in body.messages:
        if m.content and m.content.strip():
            msgs.append({"role": m.role, "content": m.content})
    if not msgs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息内容为空")
    payload = body.model_dump()
    return StreamingResponse(
        _sse_generator(payload, msgs),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
