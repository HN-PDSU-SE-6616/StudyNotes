"""Embedding 服务（sentence-transformers 本地 BGE 系列，懒加载单例）

依赖 requirements-ai.txt；模型加载较重，仅在被调用时加载，
API 进程不主动导入 torch（避免拖慢启动）。
"""
import logging
import threading
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None


def is_configured() -> bool:
    return bool(settings.embedding_model)


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # noqa: F841
                raise RuntimeError(
                    "未安装 AI 依赖，请先执行: pip install -r requirements-ai.txt"
                ) from exc
            if not settings.embedding_model:
                raise RuntimeError("未配置 EMBEDDING_MODEL（.env）")
            logger.info("加载 Embedding 模型: %s", settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
    return _model


def dimension() -> int:
    model = _load_model()
    return model.get_sentence_embedding_dimension() or 1024


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """批量文本向量化（返回 list[list[float]]）"""
    if not texts:
        return []
    model = _load_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
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
    """释放模型（测试用）"""
    global _model
    _model = None
