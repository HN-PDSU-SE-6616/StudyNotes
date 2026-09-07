"""RAG 问答服务：检索 → 组装上下文 → LLM（OpenAI 兼容，如 DeepSeek）"""
import logging
from typing import Any, Optional

from app.core.config import settings
from app.services import embedding, qdrant_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个知识库问答助手。请仅依据提供的【参考资料】回答用户问题；"
    "如果资料不足以回答，请直接说明“资料中未找到相关内容”，不要编造。"
    "引用资料时请在句末使用形如 [1] 的角标（编号与参考资料序号对应）。"
)


def _llm_client():
    if not settings.llm_api_key:
        raise RuntimeError("未配置 LLM_API_KEY，无法生成回答")
    from openai import OpenAI

    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _build_context(scored: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, item in enumerate(scored, start=1):
        p = item.get("payload") or {}
        header = p.get("note_title") or "未知笔记"
        heading = p.get("heading_path")
        if heading:
            header = f"{header} > {heading}"
        text = (p.get("text") or "")[:2000]
        blocks.append(f"[{i}] 《{header}》\n{text}")
    return "\n\n---\n\n".join(blocks)


def search_only(
    question: str,
    accessible_project_ids: list[str],
    top_k: int = 8,
) -> dict:
    """仅检索知识库（供 Agent 工具调用，不二次调用 LLM）。

    返回: {"found": bool, "sources": [...], "context": "【参考资料】文本"}
    - embedding 未配置 → RuntimeError（上层可读提示）；
    - 无可访问项目 / 无命中 → found=False。
    """
    if not question.strip():
        raise ValueError("问题不能为空")
    if not embedding.is_configured():
        raise RuntimeError("未配置 EMBEDDING_MODEL，知识库检索不可用")
    if not accessible_project_ids:
        return {"found": False, "sources": [], "context": ""}

    qdrant_service.ensure_collections(vector_size=embedding.dimension())
    query_vector = embedding.embed_query(question)
    results = qdrant_service.search_notes(query_vector, accessible_project_ids, limit=top_k)
    if not results:
        return {"found": False, "sources": [], "context": ""}

    sources = []
    for item in results:
        p = item.get("payload") or {}
        sources.append({
            "note_id": p.get("note_id"),
            "title": p.get("note_title") or "",
            "slug": p.get("note_slug") or "",
            "project_id": p.get("project_id"),
            "heading_path": p.get("heading_path") or "",
            "page": p.get("page"),
            "anchor": p.get("anchor") or "",
            "score": round(item.get("score", 0.0), 4),
            "excerpt": (p.get("text") or "")[:200],
            "content": (p.get("text") or "")[:1600],
        })
    return {"found": True, "sources": sources, "context": _build_context(results)}


def ask(
    question: str,
    accessible_project_ids: list[str],
    top_k: int = 8,
) -> dict[str, Any]:
    """RAG 问答（同步：embedding/LLM 均为阻塞调用，由 API 线程池执行）。
    注意：需在 embedding 模型配置完成后调用；否则抛 RuntimeError。
    """
    if not accessible_project_ids:
        return {
            "answer": "当前没有任何可访问的知识库内容，无法回答。",
            "sources": [],
        }
    res = search_only(question, accessible_project_ids, top_k=top_k)
    if not res["found"]:
        return {"answer": "未在知识库中找到与问题相关的内容。", "sources": []}

    client = _llm_client()
    completion = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"【参考资料】\n{res['context']}\n\n【问题】{question}"},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    answer = completion.choices[0].message.content or ""
    return {"answer": answer, "sources": res["sources"]}
