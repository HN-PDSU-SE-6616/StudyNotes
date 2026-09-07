"""Embedding 服务：本地 sentence-transformers 或 OpenAI 兼容远程 API（模型可按环境自配）

配置（安装者按硬件/成本自选，见 .env.example）：
- EMBEDDING_PRESET：从下方 PRESETS 选取（小/中/大模型），自动带入 model 名与维度；
- EMBEDDING_MODEL / EMBEDDING_DIM：显式覆盖（优先于 preset）；
- EMBEDDING_PROVIDER=local|api：
  · local 在机器上加载 sentence-transformers（CPU 小模型建议 bge-small-zh）；
  · api 通过 EMBEDDING_BASE_URL/API_KEY/MODEL 调 OpenAI 兼容接口。

维度与 Qdrant collection 需一致：不匹配时 qdrant_service.ensure_collections 会报错，
按提示运行 scripts/rebuild_embeddings.py 重建并重索引即可。
"""
import logging
import threading
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============ 模型预设（小/中/大，可自由组合 local/api） ============
PRESETS: dict[str, dict] = {
    # ---- 本地 sentence-transformers（BGE 中文系列，CPU 友好度递增）----
    "bge-small-zh": {
        "model": "BAAI/bge-small-zh-v1.5", "dim": 512,
        "note": "中文·轻量（~100MB，CPU 推荐，速度最快）",
    },
    "bge-base-zh": {
        "model": "BAAI/bge-base-zh-v1.5", "dim": 768,
        "note": "中文·中量（精度/资源平衡）",
    },
    "bge-large-zh": {
        "model": "BAAI/bge-large-zh-v1.5", "dim": 1024,
        "note": "中文·重量（精度最高，资源占用大）",
    },
    "bge-m3": {
        "model": "BAAI/bge-m3", "dim": 1024,
        "note": "多语言·重量（中文效果好；本地需较高内存，30 系显卡/大内存体验佳）",
    },
    "bge-small-en": {
        "model": "BAAI/bge-small-en-v1.5", "dim": 384,
        "note": "英文·轻量",
    },
    "bge-base-en": {
        "model": "BAAI/bge-base-en-v1.5", "dim": 768,
        "note": "英文·中量",
    },
    # ---- 远程 API（OpenAI 兼容，需 EMBEDDING_PROVIDER=api） ----
    "openai-3-small": {
        "model": "text-embedding-3-small", "dim": 1536,
        "note": "远程·OpenAI 3 small（费用低）",
    },
    "openai-3-large": {
        "model": "text-embedding-3-large", "dim": 3072,
        "note": "远程·OpenAI 3 large（精度高）",
    },
}


def preset_info(name: str) -> Optional[dict]:
    """返回预设信息 {model, dim, note}；未知名称返回 None"""
    p = PRESETS.get(name or "")
    return dict(p) if p else None


def model_name() -> str:
    """生效的模型名：显式 EMBEDDING_MODEL 优先，其次 preset 推断"""
    if settings.embedding_model:
        return settings.embedding_model
    p = preset_info(settings.embedding_preset)
    return (p or {}).get("model", "")


def _preset_dim() -> Optional[int]:
    p = preset_info(settings.embedding_preset)
    return (p or {}).get("dim")


def provider() -> str:
    if settings.embedding_provider.lower() in ("api", "remote", "openai") or (
        settings.embedding_base_url and settings.embedding_api_key
    ):
        return "api"
    return "local"


def is_configured() -> bool:
    if not model_name():
        return False
    if provider() == "api":
        return bool(settings.embedding_base_url and settings.embedding_api_key)
    return True


_lock = threading.Lock()
_model = None
_api_dim: Optional[int] = None  # 远程接口首次返回后缓存维度
_BATCH = 64


def _load_model():
    """本地模型懒加载（仅 local provider 使用）"""
    global _model
    if _model is not None:
        return _model
    name = model_name()
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # noqa: F841
                raise RuntimeError(
                    "未安装本地 AI 依赖（torch/sentence-transformers）。"
                    "请用 ENABLE_AI=1 构建镜像，或改用 EMBEDDING_PROVIDER=api 远程接口。"
                ) from exc
            logger.info("加载本地 Embedding 模型: %s", name)
            _model = SentenceTransformer(name)
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
        resp = client.embeddings.create(model=model_name(), input=texts)
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
    # 1) 显式配置；2) preset 推断；3) 已缓存实际维度；4) 兜底 1024
    if settings.embedding_dim:
        return int(settings.embedding_dim)
    if _preset_dim():
        return int(_preset_dim())
    if _api_dim:
        return _api_dim
    if provider() == "api":
        logger.warning("未配置 EMBEDDING_DIM，按 1024 处理；首次向量化后将按实际维度对齐")
        return 1024
    model = _load_model()
    try:
        return model.get_sentence_embedding_dimension() or 1024
    except Exception:  # noqa: BLE001
        return _preset_dim() or 1024


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
