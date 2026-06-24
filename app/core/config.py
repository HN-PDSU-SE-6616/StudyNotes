"""应用配置 - 所有配置项可通过 .env 文件或环境变量覆盖"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置项"""

    # --- 应用基础 ---
    app_name: str = "Taot 知识库"
    api_prefix: str = "/Taot"

    # --- JWT 认证 ---
    secret_key: str = "change-me-in-production-use-env-var"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 小时
    refresh_token_expire_days: int = 7

    # --- 数据库 ---
    database_url: str = "sqlite+aiosqlite:///./blog.db"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- 旧版笔记数据目录（用于导入 Wolai 导出的 HTML 笔记）---
    notes_data_path: str = "data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
