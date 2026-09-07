"""pytest 全局 fixture：独立测试库 taot_test + TestClient

- 顶部即在导入 app 前将 DATABASE_URL 指向独立测试库（环境变量优先于 .env）；
- 会话级 fixture 启动 TestClient（触发 lifespan → alembic upgrade head 作用于测试库）；
- 提供随机用户注册 helper，保证多次运行互不冲突。
"""
import asyncio
import os
import uuid
from pathlib import Path

# 允许测试在项目根以相对 .env 运行
_root = Path(__file__).resolve().parent.parent
os.chdir(_root)

try:
    from dotenv import load_dotenv

    load_dotenv(_root / ".env")
except Exception:  # noqa: BLE001
    pass

import pytest  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

BASE_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://taot:taot@localhost:5432/taot"
)
# 注意：str(URL) 会掩码密码为 ***，必须用 render_as_string(hide_password=False)
TEST_DB_URL = make_url(BASE_DB_URL).set(database="taot_test").render_as_string(
    hide_password=False
)


def _ensure_test_db() -> None:
    """幂等创建 taot_test 数据库（连接基础库执行 DDL）"""
    base = make_url(BASE_DB_URL)

    async def _run():
        import asyncpg

        conn = await asyncpg.connect(
            host=base.host,
            port=base.port or 5432,
            user=base.username,
            password=base.password,
            database=base.database,
        )
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", "taot_test"
            )
            if not exists:
                await conn.execute('CREATE DATABASE "taot_test"')
        finally:
            await conn.close()

    asyncio.run(_run())


_ensure_test_db()
os.environ["DATABASE_URL"] = TEST_DB_URL


def make_user(tag: str) -> dict:
    suffix = uuid.uuid4().hex[:6]
    return {
        "username": f"{tag}_{suffix}",
        "email": f"{tag}_{suffix}@test.dev",
        "password": "Passw0rd!",
        "display_name": f"{tag} {suffix}",
    }


@pytest.fixture(scope="session")
def client():
    """会话级 API 客户端（含 lifespan：迁移 + Qdrant 连接）"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def register(client):
    """注册 helper：返回 (headers, user)"""

    def _register(tag: str = "u"):
        user = make_user(tag)
        resp = client.post("/api/v1/auth/register", json=user)
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, user

    return _register
