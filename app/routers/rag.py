"""RAG 问答路由：向量检索 + LLM（DeepSeek OpenAI 兼容）"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel
from starlette.concurrency import run_in_threadpool

from app.core.permissions import PermissionChecker, get_permission_checker
from app.services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["AI 问答"])


class AskRequest(SQLModel):
    question: str
    project_id: str | None = None  # 可选：限定在单个项目内检索
    top_k: int = 8


class AskResponse(SQLModel):
    answer: str
    sources: list[dict]


@router.post("/ask", response_model=AskResponse, summary="知识库问答（带引用）")
async def ask(
    body: AskRequest,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    """基于可访问知识库内容作答，sources 提供跳转锚点"""
    accessible = await perm.get_accessible_project_ids(include_read=True)
    if body.project_id:
        if body.project_id not in accessible:
            # 校验用户对指定项目可读（防止泄漏）
            from app.models.org import OrgRole

            await perm.require_project_role(body.project_id, OrgRole.REPORTER.value)
        accessible = [body.project_id]

    try:
        # embedding/LLM 阻塞，放入线程池避免阻塞事件循环
        result = await run_in_threadpool(
            rag_service.ask,
            body.question,
            accessible,
            max(1, min(body.top_k, 20)),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return AskResponse(answer=result["answer"], sources=result["sources"])
