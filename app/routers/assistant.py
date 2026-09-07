"""AI 助手对话代理（Agent：工具 + 会话上下文 + 相似问题热缓存）

- POST /assistant/chat           整段返回（自由对话 / 知识库问答外的通用对话）
- POST /assistant/chat/stream    SSE 流式（data: {json} 行，末尾 data: [DONE]）
- POST /assistant/context/clear  清空指定会话上下文（session_id）

模型/密钥统一走 .env（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL），请求体不再接收
base_url/api_key/model 覆盖（保留字段仅为兼容，忽略不生效）。
请求体：
- messages            stateless 模式的完整消息（无 session_id 时使用）
- system              系统提示（可空）
- session_id          可选：开启服务端会话记忆（此时请只传本轮问题）
- tools               bool，默认 true：启用工具函数（天气/IP/系统/网页等）
- client_context      浏览器端环境信息（供 get_system_info scope=client）
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import SQLModel

from app.core.deps import get_optional_user
from app.models.user import User
from app.services import agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["AI 助手"])

STREAM_CHUNK = 12  # 回放/缓存文本的分片字符数


class ChatMessage(SQLModel):
    role: str  # system / user / assistant
    content: str


class ChatRequest(SQLModel):
    messages: list[ChatMessage] = []
    temperature: float = 0.7
    system: Optional[str] = None
    session_id: Optional[str] = None
    tools: bool = True
    client_context: Optional[dict] = None


class ClearContextRequest(SQLModel):
    session_id: str


class ChatResponse(SQLModel):
    reply: str
    model: str
    cached: bool = False
    used_tools: bool = False


def _uid(user: Optional[User]) -> str:
    return str(user.id) if user else "anon"


def _question_of(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user" and (m.get("content") or "").strip():
            return m["content"].strip()
    return ""


def _assemble(body: ChatRequest) -> tuple[list[dict], list[dict], str]:
    """构建 stateless messages；返回 (history_messages, working_messages, question)"""
    msgs: list[dict] = []
    if body.system and body.system.strip():
        msgs.append({"role": "system", "content": body.system.strip()})
    for m in body.messages:
        if m.content and m.content.strip() and m.role in ("system", "user", "assistant"):
            msgs.append({"role": m.role, "content": m.content})
    question = _question_of(msgs)
    return msgs, list(msgs), question


def _stream_chunks(text: str):
    for i in range(0, len(text), STREAM_CHUNK):
        yield text[i:i + STREAM_CHUNK]


@router.post("/chat", response_model=ChatResponse, summary="AI 对话（工具+缓存+会话）")
async def chat(body: ChatRequest, user: Optional[User] = Depends(get_optional_user)):
    msgs, _, question = _assemble(body)
    if not msgs or not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")
    uid = _uid(user)
    session_mode = False
    history: list[dict] = []
    if body.session_id:
        user_msgs = [m for m in msgs if m["role"] == "user"]
        if len(user_msgs) == 1:
            session_mode = True
            history = await agent.history_get(uid, body.session_id)
            msgs = [m for m in msgs if m["role"] == "system"] + history + user_msgs
    try:
        cached = await agent.cache_get(uid, question)
        if cached:
            if session_mode:
                await agent.history_append(uid, body.session_id, question, cached)
            return ChatResponse(reply=cached, model="cache", cached=True)
        reply, model, used_tools = await asyncio.to_thread(
            agent.run_agent, msgs,
            temperature=body.temperature,
            tools_enabled=body.tools,
            client_context=body.client_context,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat 失败: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 调用失败: {type(exc).__name__}: {exc}",
        )
    await agent.cache_put(uid, question, reply)
    if session_mode:
        await agent.history_append(uid, body.session_id, question, reply)
    return ChatResponse(reply=reply, model=model, used_tools=used_tools)


@router.post("/chat/stream", summary="AI 对话流式（SSE，工具/缓存/会话同 /chat）")
async def chat_stream(body: ChatRequest, user: Optional[User] = Depends(get_optional_user)):
    msgs, _, question = _assemble(body)
    if not msgs or not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")
    uid = _uid(user)
    session_mode = False
    if body.session_id:
        user_msgs = [m for m in msgs if m["role"] == "user"]
        if len(user_msgs) == 1:
            session_mode = True
            history = await agent.history_get(uid, body.session_id)
            msgs = [m for m in msgs if m["role"] == "system"] + history + user_msgs
    payload = body

    async def sse():
        text = ""
        try:
            cached = await agent.cache_get(uid, question)
            if cached:
                text = cached
            else:
                text, _model, _used_tools = await asyncio.to_thread(
                    agent.run_agent, msgs,
                    temperature=payload.temperature,
                    tools_enabled=payload.tools,
                    client_context=payload.client_context,
                )
                if not text:
                    text = "（空回复）"
                await agent.cache_put(uid, question, text)
            for part in _stream_chunks(text):
                yield f"data: {json.dumps({'delta': part}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.004)
            if session_mode:
                await agent.history_append(uid, payload.session_id, question, text)
        except RuntimeError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.warning("stream 失败: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/context/clear", summary="清空当前会话上下文（session_id 必填）")
async def context_clear(body: ClearContextRequest, user: Optional[User] = Depends(get_optional_user)):
    if not body.session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id 不能为空")
    await agent.history_clear(_uid(user), body.session_id)
    return {"ok": True, "session_id": body.session_id}
