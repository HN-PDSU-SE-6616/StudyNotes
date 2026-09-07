"""Qdrant 向量库服务：collection 管理、chunk 写入/删除/检索

两个 collection：
- kb_notes：笔记 chunk（payload 含权限过滤字段）
- user_profiles：用户兴趣向量（推荐）
"""
import logging
import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.services import embedding

logger = logging.getLogger(__name__)

KB_NOTES_COLLECTION = "kb_notes"
USER_PROFILES_COLLECTION = "user_profiles"

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def ensure_collections(vector_size: Optional[int] = None) -> None:
    """幂等创建 collection（含权限过滤所需 payload index）；已存在时校验维度对齐"""
    client = get_client()
    dim = vector_size or 1024
    for name in (KB_NOTES_COLLECTION, USER_PROFILES_COLLECTION):
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )
            logger.info("Qdrant collection 已创建: %s (dim=%s)", name, dim)
        elif vector_size is not None:
            # 校验与向量库对齐：维度不一致给出可操作的报错，避免静默写入失败
            info = client.get_collection(name)
            exist_dim = None
            try:
                exist_dim = info.config.params.vectors.size
            except Exception:  # noqa: BLE001
                exist_dim = getattr(getattr(info.config.params.vectors, "size", None), None, None)
            if exist_dim and exist_dim != dim:
                raise RuntimeError(
                    f"Qdrant collection「{name}」当前维度 {exist_dim} 与 Embedding 输出维度 "
                    f"{dim} 不一致。请对齐 EMBEDDING_MODEL/EMBEDDING_DIM 配置，或删除 collection/清空 "
                    f"qdrant_storage 卷后重建。"
                )

    # kb_notes 权限/路由过滤字段索引
    indexes = [
        ("note_id", models.PayloadSchemaType.KEYWORD),
        ("project_id", models.PayloadSchemaType.KEYWORD),
        ("org_id", models.PayloadSchemaType.KEYWORD),
        ("owner_id", models.PayloadSchemaType.INTEGER),
        ("is_public", models.PayloadSchemaType.BOOL),
    ]
    for field, schema in indexes:
        try:
            client.create_payload_index(
                collection_name=KB_NOTES_COLLECTION,
                field_name=field,
                field_schema=schema,
            )
        except Exception:  # noqa: BLE001 已存在时忽略
            pass


def upsert_note_chunks(
    note: dict[str, Any],
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
) -> int:
    """幂等写入单篇笔记的全部 chunk（调用方需先删除旧 chunk）"""
    if not chunks or not vectors or len(chunks) != len(vectors):
        return 0
    client = get_client()
    points = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        point_id = f"{note['id']}:{i}"
        payload = {
            "text": chunk.get("text", ""),
            "note_id": note["id"],
            "project_id": note["project_id"],
            "org_id": note["org_id"],
            "owner_id": note["owner_id"],
            "is_public": bool(note.get("is_public", False)),
            "note_title": note.get("title", ""),
            "note_slug": note.get("slug", ""),
            "heading_path": chunk.get("heading_path", ""),
            "page": chunk.get("page"),
            "anchor": chunk.get("anchor", ""),
            "chunk_index": i,
            "block_start": chunk.get("block_start"),
            "block_end": chunk.get("block_end"),
        }
        points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
    client.upsert(collection_name=KB_NOTES_COLLECTION, points=points)
    return len(points)


def delete_note_index(note_id: str) -> None:
    client = get_client()
    try:
        client.delete(
            collection_name=KB_NOTES_COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[
                    models.FieldCondition(key="note_id", match=models.MatchValue(value=note_id)),
                ])
            ),
        )
    except Exception:  # noqa: BLE001
        logger.warning("删除笔记向量失败: %s", note_id, exc_info=True)


def build_access_filter(accessible_project_ids: list[str]) -> models.Filter:
    """权限过滤：项目可访问 或 笔记公开"""
    must_not = None
    return models.Filter(
        should=[
            models.FieldCondition(
                key="project_id",
                match=models.MatchAny(any=accessible_project_ids),
            ),
            models.FieldCondition(key="is_public", match=models.MatchValue(value=True)),
        ],
    )


def search_notes(
    query_vector: list[float],
    accessible_project_ids: list[str],
    limit: int = 8,
    exclude_owner_id: Optional[int] = None,
    exclude_note_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """在 kb_notes 上按向量检索（带权限过滤）"""
    client = get_client()
    must_not = []
    if exclude_owner_id is not None:
        must_not.append(
            models.FieldCondition(key="owner_id", match=models.MatchValue(value=exclude_owner_id))
        )
    if exclude_note_ids:
        must_not.append(
            models.FieldCondition(key="note_id", match=models.MatchAny(any=exclude_note_ids))
        )
    flt = build_access_filter(accessible_project_ids)
    if must_not:
        flt.must_not = must_not

    results = client.search(
        collection_name=KB_NOTES_COLLECTION,
        query_vector=query_vector,
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    return [
        {
            "score": r.score,
            "payload": r.payload,
        }
        for r in results
    ]


def upsert_user_profile(user_id: int, vector: list[float]) -> None:
    """写/更新用户兴趣向量"""
    client = get_client()
    client.upsert(
        collection_name=USER_PROFILES_COLLECTION,
        points=[models.PointStruct(id=str(user_id), vector=vector, payload={"user_id": user_id})],
    )
