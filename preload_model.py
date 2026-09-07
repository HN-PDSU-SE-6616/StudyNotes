"""本地 Embedding 模型启动预热（Docker backend/worker 入口调用）

作用：启动时将 sentence-transformers 模型载入内存并把权重固化到 HF 缓存卷，
避免首次问答/索引任务现场联网下载与长时间加载；任何失败仅告警不阻塞启动。

用法：python /app/preload_model.py
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("preload_model")

from app.core.config import settings  # noqa: E402
from app.services import embedding  # noqa: E402


def main() -> int:
    if embedding.provider() != "local":
        print("EMBEDDING_PROVIDER=api：本地预加载跳过（远程按请求调用）")
        return 0
    if not embedding.is_configured():
        print("EMBEDDING_MODEL 未配置：本地预加载跳过")
        return 0
    try:
        dim = embedding.dimension()
        embedding.embed_query("预热")
        print(f"Embedding 预加载完成 model={settings.embedding_model} dim={dim}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding 预加载失败（忽略，运行期将重试）: %s", exc)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
