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


def test_assistant_chat_stream_sse(client, register, monkeypatch):
    """SSE 流式：逐 delta 事件下发并以 [DONE] 结束（用 yield 的生成器）"""
    headers, _ = register("ast_sse")
    import app.routers.assistant as assistant_router

    def fake_stream(messages, base_url=None, api_key=None, model=None, temperature=0.7):
        for piece in ("你", "好", "！流式回复。"):
            yield piece

    monkeypatch.setattr(assistant_router, "llm_chat_stream", fake_stream)
    with client.stream(
        "POST", "/api/v1/assistant/chat/stream", headers=headers,
        json={"messages": [{"role": "user", "content": "你好"}], "model": "m"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = "".join(resp.iter_text())
    assert '"delta": "你"' in body
    assert '"delta": "好"' in body
    assert "[DONE]" in body


def test_assistant_stream_error_event(client, register, monkeypatch):
    """流式过程 RuntimeError → 以 error 事件下发且仍 [DONE]"""
    headers, _ = register("ast_sse_e")
    import app.routers.assistant as assistant_router

    def boom(*_a, **_k):
        raise RuntimeError("密钥缺失")

    monkeypatch.setattr(assistant_router, "llm_chat_stream", boom)
    with client.stream(
        "POST", "/api/v1/assistant/chat/stream", headers=headers,
        json={"messages": [{"role": "user", "content": "hi"}]},
    ) as resp:
        body = "".join(resp.iter_text())
    assert "error" in body and "密钥缺失" in body
    assert "[DONE]" in body


def test_embedding_presets_resolution(monkeypatch):
    """预设解析：preset 自动带入模型/维度；显式配置优先"""
    from app.core.config import settings

    # 模拟未显式配置维度（.env 可能已设 EMBEDDING_DIM）
    monkeypatch.setattr(settings, "embedding_dim", None)
    monkeypatch.setattr(settings, "embedding_model", "")
    monkeypatch.setattr(settings, "embedding_preset", "bge-small-zh")
    monkeypatch.setattr(settings, "embedding_provider", "local")
    assert embedding.model_name() == "BAAI/bge-small-zh-v1.5"
    assert embedding.dimension() == 512

    # 中/大预设
    monkeypatch.setattr(settings, "embedding_preset", "bge-base-zh")
    assert embedding.model_name() == "BAAI/bge-base-zh-v1.5"
    assert embedding.dimension() == 768
    monkeypatch.setattr(settings, "embedding_preset", "bge-large-zh")
    assert embedding.dimension() == 1024
    monkeypatch.setattr(settings, "embedding_preset", "bge-m3")
    assert embedding.model_name() == "BAAI/bge-m3"

    # 显式模型优先于 preset
    monkeypatch.setattr(settings, "embedding_model", "local-path/custom-model")
    monkeypatch.setattr(settings, "embedding_preset", "bge-small-zh")
    assert embedding.model_name() == "local-path/custom-model"
    # 显式维度优先于 preset 维度
    monkeypatch.setattr(settings, "embedding_dim", 640)
    assert embedding.dimension() == 640

    # 未知预设且无显式配置 → 未配置（容错）
    monkeypatch.setattr(settings, "embedding_model", "")
    monkeypatch.setattr(settings, "embedding_preset", "not-exist")
    monkeypatch.setattr(settings, "embedding_dim", None)
    assert embedding.is_configured() is False

    # 预设清单完整（含本地小/中/大与远程项）
    for key in ("bge-small-zh", "bge-base-zh", "bge-large-zh", "bge-m3",
                "bge-small-en", "bge-base-en", "openai-3-small", "openai-3-large"):
        p = embedding.preset_info(key)
        assert p and p["model"] and p["dim"] > 0


def test_embedding_provider_configured(monkeypatch):
    """远程 provider 需 base_url/api_key/model 齐备才视为已配置"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "embedding_model", "")
    monkeypatch.setattr(settings, "embedding_preset", "")
    monkeypatch.setattr(settings, "embedding_dim", None)
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
