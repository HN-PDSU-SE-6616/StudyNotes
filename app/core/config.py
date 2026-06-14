"""应用配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置项"""

    app_name: str = "Taot 知识库"
    api_prefix: str = "/Taot"
    secret_key: str = "change-me-in-production-use-env-var"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 7
    database_url: str = "sqlite+aiosqlite:///./blog.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
