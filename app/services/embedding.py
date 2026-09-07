"""Embedding 服务：本地 sentence-transformers 或 OpenAI 兼容远程 API

provider（.env EMBEDDING_PROVIDER）：
- local：加载 sentence-transformers（BGE-M3 等），懒加载单例，不阻塞 API 启动；
- api ：通过 EMBEDDING_BASE_URL/EMBEDDING_API_KEY/EMBEDDING_MODEL 调用
        OpenAI 兼容的 embeddings 接口（OpenAI/SiliconFlow/DeepSeek 等）。

维度对齐：EMBEDDING_DIM 建议显式配置；collection 首次按实际向量维度创建，
后续若与配置不一致会在 qdrant_service.ensure_collections 中给出明确报错。
"""
import logging
import threading
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None
_api_dim: Optional[int] = None  # 远程接口首次返回后缓存维度

_BATCH = 64


def provider() -> str:
    if settings.embedding_provider.lower() in ("api", "remote", "openai") or (
        settings.embedding_base_url and settings.embedding_api_key
    ):
        return "api"
    return "local"


def is_configured() -> bool:
    if not settings.embedding_model:
        return False
    if provider() == "api":
        return bool(settings.embedding_base_url and settings.embedding_api_key)
    return True


def _load_model():
    """本地模型懒加载（仅 local provider 使用）"""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # noqa: F841
                raise RuntimeError(
                    "未安装本地 AI 依赖，请执行 pip install -r requirements-ai.txt，"
                    "或改用远程 Embedding（配置 EMBEDDING_PROVIDER=api + EMBEDDING_BASE_URL/API_KEY/MODEL）"
                ) from exc
            logger.info("加载本地 Embedding 模型: %s", settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
    return _model


def _api_client():
    try:
        from openai import OpenAI
    except ImportError as exc:  # noqa: F841
        raise RuntimeError("未安装 openai SDK，无法调用远程 Embedding") from exc
    return OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url or None,
        timeout=60.0,
    )


def _api_embed(texts: list[str]) -> list[list[float]]:
    global _api_dim
    client = _api_client()
    try:
        resp = client.embeddings.create(model=settings.embedding_model, input=texts)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"远程 Embedding 调用失败: {type(exc).__name__}: {exc}。"
            "请检查 EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL。"
        ) from exc
    data = sorted(resp.data, key=lambda d: d.index)
    vectors = [list(d.embedding) for d in data]
    if vectors and _api_dim is None:
        _api_dim = len(vectors[0])
    return vectors


def dimension() -> int:
    """当前 embedding 输出维度（与 Qdrant collection 对齐用）"""
    if provider() == "api":
        if settings.embedding_dim:
            return int(settings.embedding_dim)
        if _api_dim:
            return _api_dim
        logger.warning("未配置 EMBEDDING_DIM，按 1024 处理；首次向量化后将按实际维度对齐")
        return 1024
    model = _load_model()
    return model.get_sentence_embedding_dimension() or 1024


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """批量文本向量化（返回 list[list[float]]）；文本为空返回 []"""
    texts = [t for t in texts if t]
    if not texts:
        return []
    if provider() == "api":
        out: list[list[float]] = []
        bs = batch_size or _BATCH
        for i in range(0, len(texts), bs):
            out.extend(_api_embed(texts[i:i + bs]))
        return out

    model = _load_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size or 32,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """查询文本向量化（单条）"""
    results = embed_texts([text])
    return results[0]


def unload() -> None:
    """释放本地模型（测试用）"""
    global _model
    _model = None
