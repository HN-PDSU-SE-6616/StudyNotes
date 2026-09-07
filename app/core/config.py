"""应用配置 - 所有配置项可通过 .env 文件或环境变量覆盖"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置项"""

    # --- 应用基础 ---
    app_name: str = "Taot 知识库"
    api_prefix: str = "/api/v1"

    # --- JWT 认证 ---
    secret_key: str = "change-me-in-production-use-env-var"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 小时
    refresh_token_expire_days: int = 7

    # --- 数据库（PostgreSQL） ---
    database_url: str = "postgresql+asyncpg://taot:taot@localhost:5432/taot"

    # --- Qdrant 向量库 ---
    qdrant_url: str = "http://localhost:6333"

    # --- Redis（Celery broker/result + 推荐缓存） ---
    redis_url: str = "redis://localhost:6379/0"

    # --- 对象存储 ---
    # LocalFS 根目录；未来切 S3/MinIO 时改为 storage_provider=s3 + s3_bucket 等
    storage_provider: str = "local"
    storage_root: str = "storage"

    # --- Embedding（空值表示 RAG/推荐功能关闭） ---
    embedding_model: str = ""
    # provider: local=本地 sentence-transformers；api=OpenAI 兼容接口（SiliconFlow/OpenAI 等）
    embedding_provider: str = "local"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    # 远程接口向量的维度；建议显式配置并与 Qdrant collection 维度对齐（默认 1024）
    embedding_dim: Optional[int] = None
    # --- LLM（OpenAI 兼容接口，如 DeepSeek） ---
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- 旧版笔记数据目录（仅离线归档参考，不再自动挂载） ---
    notes_data_path: str = "data"

    # 允许文档解析的扩展名白名单
    allowed_doc_extensions: list[str] = [
        ".md", ".html", ".htm", ".txt", ".csv", ".log",
        ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".less",
        ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php", ".r",
        ".swift", ".kt", ".scala", ".lua", ".dart", ".cs",
        ".sql", ".sh", ".bash", ".zsh", ".json", ".yaml", ".yml", ".toml",
        ".xml", ".ini", ".cfg", ".conf", ".bat", ".ps1",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico",
        ".xlsx", ".xls", ".docx", ".doc", ".pdf", ".pptx", ".ppt", ".xmind",
        ".zip",
    ]

    # 每个文件的解析超时保护（秒，防止超大文件阻塞 worker）
    parse_max_file_size_mb: int = 100

    # --- 推荐权重（加权混合：画像/行为/热度/时效，和须≈1） ---
    rec_w_profile: float = 0.40
    rec_w_read: float = 0.25
    rec_w_pop: float = 0.25
    rec_w_fresh: float = 0.10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        # list 类型（如 CORS_ORIGINS）使用 JSON 数组字符串注入


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
