"""AI 助手通用对话代理（OpenAI 兼容 /chat/completions）

用于前端“悬浮 AI 助手”的自由对话：请求体可携带 base_url/model/api_key 覆盖
后端默认配置（前端可把配置存在浏览器本地做个性化），未携带时回落 .env 的
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。密钥不落库、不打日志。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
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


def llm_chat(
    messages: list[dict],
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> tuple[str, str]:
    """同步调用 OpenAI 兼容 chat completions，返回 (reply, model)"""
    from openai import OpenAI

    cfg_base = base_url or settings.llm_base_url
    cfg_key = api_key or settings.llm_api_key
    cfg_model = model or settings.llm_model
    if not cfg_key:
        raise RuntimeError("未配置 LLM API Key：请在悬浮助手设置中填写，或在 .env 配置 LLM_API_KEY")
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
