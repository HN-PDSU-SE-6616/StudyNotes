"""批量删除/清空项目 + assistant 通用对话代理 + embedding 配置容错"""
import uuid

from app.services import embedding


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _first_pid(client, headers):
    orgs = client.get("/api/v1/orgs/", headers=headers).json()
    projects = client.get(f"/api/v1/orgs/{orgs[0]['id']}/projects/", headers=headers).json()
    return projects[0]["id"]


def _make_leaf(client, headers, pid, parent, title):
    return client.post(
        f"/api/v1/projects/{pid}/notes/",
        json={"title": title, "icon": "doc", "parent_id": parent},
        headers=headers,
    ).json()


def test_batch_delete_and_clear_project(client, register):
    headers, _ = register("bulk")
    pid = _first_pid(client, headers)

    root1 = _make_leaf(client, headers, pid, None, "根A")
    _make_leaf(client, headers, pid, root1["id"], "子A1")
    root2 = _make_leaf(client, headers, pid, None, "根B")
    _make_leaf(client, headers, pid, root2["id"], "子B1")

    # 批量删除（子节点可独立删除）
    r = client.post("/api/v1/notes/batch-delete", headers=headers,
                    json={"note_ids": [root1["id"], root2["id"]]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted_count"] == 2
    assert body["failed"] == []
    tree = client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json()
    assert tree == []

    # 重新导入两棵后，用「清空项目」整体清理
    for title in ("根C", "根D"):
        _make_leaf(client, headers, pid, None, title)
    cr = client.delete(f"/api/v1/projects/{pid}/notes/", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["deleted_roots"] == 2
    tree2 = client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json()
    assert tree2 == []


def test_batch_delete_ignores_invisible(client, register):
    """批量删除遇到不可见/不存在 id：计入 failed，不报 404 中断"""
    headers, _ = register("bulk_b")
    pid = _first_pid(client, headers)
    root = _make_leaf(client, headers, pid, None, "我的")
    other_headers, _ = register("bulk_other")

    r = client.post("/api/v1/notes/batch-delete", headers=other_headers,
                    json={"note_ids": [root["id"], "not-exist-id"]})
    assert r.status_code == 200
    assert r.json()["deleted_count"] == 0
    assert len(r.json()["failed"]) == 2

    # 原 owner 删除自己页仍可
    r2 = client.post("/api/v1/notes/batch-delete", headers=headers,
                     json={"note_ids": [root["id"]]})
    assert r2.json()["deleted_count"] == 1


def test_assistant_chat_proxy(client, register, monkeypatch):
    headers, _ = register("ast")

    captured = {}

    def fake_llm(messages, base_url=None, api_key=None, model=None, temperature=0.7):
        captured.update({"messages": messages, "base_url": base_url,
                         "api_key": api_key, "model": model})
        return "你好！我是测试助手。", (model or "mock-model")

    import app.routers.assistant as assistant_router

    monkeypatch.setattr(assistant_router, "llm_chat", fake_llm)
    r = client.post("/api/v1/assistant/chat", headers=headers, json={
        "messages": [{"role": "user", "content": "你好"}],
        "base_url": "https://x/v1",
        "api_key": "sk-test",
        "model": "deepseek-chat",
    })
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "你好！我是测试助手。"
    assert captured["base_url"] == "https://x/v1"
    assert captured["api_key"] == "sk-test"

    # LLM 侧异常 → 503 可读错误
    def boom(*_a, **_k):
        raise RuntimeError("未配置 LLM API Key：请在悬浮助手设置中填写，或在 .env 配置 LLM_API_KEY")

    monkeypatch.setattr(assistant_router, "llm_chat", boom)
    r2 = client.post("/api/v1/assistant/chat", headers=headers,
                     json={"messages": [{"role": "user", "content": "hi"}]})
    assert r2.status_code == 503
    assert "LLM_API_KEY" in r2.json()["detail"]


def test_embedding_provider_configured(monkeypatch):
    """远程 provider 需 base_url/api_key/model 齐备才视为已配置"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "embedding_model", "")
    assert embedding.is_configured() is False

    monkeypatch.setattr(settings, "embedding_model", "bge-m3")
    monkeypatch.setattr(settings, "embedding_provider", "local")
    assert embedding.provider() == "local"

    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "embedding_base_url", "")
    monkeypatch.setattr(settings, "embedding_api_key", "")
    assert embedding.is_configured() is False  # key/url 缺失视为未配置（容错跳过）

    monkeypatch.setattr(settings, "embedding_base_url", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(settings, "embedding_api_key", "sk-x")
    monkeypatch.setattr(settings, "embedding_dim", 1024)
    assert embedding.is_configured() is True
    assert embedding.provider() == "api"
    assert embedding.dimension() == 1024  # 显式配置维度与向量库对齐
