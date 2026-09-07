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
    """Agent 对话：工具循环/降级由 run_agent 承载；RuntimeError → 503 可读错误"""
    headers, _ = register("ast")
    import app.services.agent as agent_mod

    captured = {}

    def fake_agent(messages, base_url=None, api_key=None, model=None, temperature=0.7,
                   tools_enabled=True, client_context=None, rag_context=None):
        captured.update({"messages": messages, "temperature": temperature,
                         "tools_enabled": tools_enabled, "rag_context": rag_context})
        return "你好！我是测试助手。", "mock-model", False

    monkeypatch.setattr(agent_mod, "run_agent", fake_agent)
    r = client.post("/api/v1/assistant/chat", headers=headers, json={
        "messages": [{"role": "user", "content": "你好"}],
        "project_id": "proj-x",
    })
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "你好！我是测试助手。"
    assert captured["tools_enabled"] is True
    assert captured["messages"][-1]["content"] == "你好"
    # 登录用户注入知识库检索上下文（可访问项目 + 限定项目）
    rc = captured["rag_context"]
    assert rc and rc["enabled"] is True
    assert rc["project_id"] == "proj-x"

    # LLM 侧异常 → 503 可读错误
    def boom(*_a, **_k):
        raise RuntimeError("未配置 LLM API Key：请在 .env 配置 LLM_API_KEY")

    monkeypatch.setattr(agent_mod, "run_agent", boom)
    r2 = client.post("/api/v1/assistant/chat", headers=headers,
                     json={"messages": [{"role": "user", "content": "hi"}]})
    assert r2.status_code == 503
    assert "LLM_API_KEY" in r2.json()["detail"]


def test_assistant_chat_stream_sse(client, register, monkeypatch):
    """SSE 流式：run_agent 回复分片下发并以 [DONE] 结束"""
    headers, _ = register("ast_sse")
    import app.services.agent as agent_mod

    def fake_agent(*_a, **_k):
        return "这是一段用于流式验证的长回复文本。", "m", False

    monkeypatch.setattr(agent_mod, "run_agent", fake_agent)
    with client.stream(
        "POST", "/api/v1/assistant/chat/stream", headers=headers,
        json={"messages": [{"role": "user", "content": "你好"}]},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = "".join(resp.iter_text())
    assert "用于流式验证" in body  # 分片回放仍能拼接出完整内容
    assert "[DONE]" in body


def test_assistant_stream_error_event(client, register, monkeypatch):
    """流式过程 RuntimeError → 以 error 事件下发且仍 [DONE]"""
    headers, _ = register("ast_sse_e")
    import app.services.agent as agent_mod

    def boom(*_a, **_k):
        raise RuntimeError("密钥缺失")

    monkeypatch.setattr(agent_mod, "run_agent", boom)
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


# ================= 新增：Agent 工具 / 会话上下文 / 热缓存 / 目录导入改名 =================

def test_agent_tools_registry_and_handlers(monkeypatch):
    """工具注册表：五个内置工具、可执行、可扩展、错误安全"""
    from app.services import tools

    names = {t["function"]["name"] for t in tools.list_tools()}
    assert {"get_weather", "get_ip", "get_system_info",
            "fetch_web_page", "web_search", "search_knowledge_base"} <= names

    # get_system_info(scope=client) 读取注入的浏览器环境
    out = tools.execute_tool(
        "get_system_info", {"scope": "client"},
        {"client_context": {"os": "Windows 11", "cores": "16", "gpu": "ANGLE (NVIDIA)"}},
    )
    assert "Windows 11" in out and "NVIDIA" in out

    # 未知工具 / 异常均以文本返回，不抛出
    assert "未知工具" in tools.execute_tool("not_exist", {})

    # fetch_web_page：soup4 去脚本/样式只留正文
    html = ("<html><head><title>测试页</title></head>"
            "<body><script>var x=1</script>"
            "<p>正文内容段落。</p></body></html>")

    class FakeResp:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(tools, "_http_get", lambda *a, **k: FakeResp())
    out2 = tools.execute_tool("fetch_web_page", {"url": "https://example.com/a"})
    assert "标题：测试页" in out2
    assert "正文内容段落" in out2
    assert "var x" not in out2


def test_agent_cache_exact_and_similar(client, register, monkeypatch):
    """相似问题热缓存：重复/近似问题不重复调用模型；不同问题仍正常"""
    headers, _ = register("ascache")
    import app.services.agent as agent_mod

    calls = []

    def fake_agent(*_a, **_k):
        calls.append(1)
        return "这是缓存的回答内容。", "m", False

    monkeypatch.setattr(agent_mod, "run_agent", fake_agent)
    q1 = "帮我总结一下 FastAPI 的优缺点？"
    r1 = client.post("/api/v1/assistant/chat", headers=headers,
                     json={"messages": [{"role": "user", "content": q1}]}).json()
    assert r1["reply"] == "这是缓存的回答内容。"
    assert len(calls) == 1

    # 归一化后完全相同 → 直接命中缓存，不再调模型
    r2 = client.post("/api/v1/assistant/chat", headers=headers,
                     json={"messages": [{"role": "user",
                                          "content": "帮我总结一下FastAPI的优缺点"}]}).json()
    assert r2["cached"] is True
    assert r2["reply"] == r1["reply"]
    assert len(calls) == 1

    # 完全不同的问题 → 重新调用
    r3 = client.post("/api/v1/assistant/chat", headers=headers,
                     json={"messages": [{"role": "user", "content": "帮我写一个快排"}]}).json()
    assert r3["cached"] is False
    assert len(calls) == 2

    # 相似度门控单元
    assert agent_mod._is_similar("北京今天天气如何", "北京今天天气怎样") is True
    assert agent_mod._is_similar("北京今天天气如何", "帮我写快速排序算法") is False


def test_assistant_session_context_and_clear(client, register, monkeypatch):
    """会话上下文：历史注入后续对话；context/clear 可整体清空"""
    headers, _ = register("asctx")
    import app.services.agent as agent_mod

    sid = f"s-{uuid.uuid4().hex[:8]}"
    seen: list[list[str]] = []

    def fake_agent(messages, *a, **k):
        seen.append([m["content"] for m in messages if m["role"] in ("user", "assistant")])
        return f"答复{len(seen)}", "m", False

    monkeypatch.setattr(agent_mod, "run_agent", fake_agent)

    def ask(q: str):
        return client.post("/api/v1/assistant/chat", headers=headers, json={
            "messages": [{"role": "user", "content": q}], "session_id": sid,
        }).json()

    assert ask("你好介绍一下自己")["reply"] == "答复1"
    r2 = ask("你会写代码吗")
    assert r2["reply"] == "答复2"
    # 第二次对话已带上第一轮历史
    assert "你好介绍一下自己" in seen[1]
    assert "答复1" in seen[1]

    clear = client.post("/api/v1/assistant/context/clear", headers=headers,
                        json={"session_id": sid})
    assert clear.status_code == 200
    r3 = ask("今天星期几")
    assert r3["reply"] == "答复3"
    # 清空后不再注入历史
    assert seen[2] == ["今天星期几"]


def test_import_dir_renames_target_page(client, register):
    """导入目录到选中页：选中页改名为目录名并充当目录宿主（子文档成其子页、同名文档并入）"""
    headers, _ = register("imp_rn")
    pid = _first_pid(client, headers)
    target = _make_leaf(client, headers, pid, None, "待导入空页")
    folder = "《Go语言指南》"

    files = {
        f"{folder}/第一章.md": "# 第一章\n安装与第一个程序。\n".encode(),
        f"{folder}/第二章.md": "# 第二章\n并发模型。\n".encode(),
    }
    r = client.post(f"/api/v1/projects/{pid}/import", headers=headers,
                    data={"target_note_id": target["id"]},
                    files=[("files", (p, c, "text/markdown")) for p, c in files.items()])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_renamed"] is True
    assert body["target_title"] == folder
    assert body["root_note_id"] == target["id"]

    tree = client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json()
    root = next(n for n in tree if n["id"] == target["id"])
    assert root["title"] == folder
    children = {c["title"] for c in (root.get("children") or [])}
    assert children == {"第一章", "第二章"}

    # 同名文档（与目录同名 .md）内容并入宿主页；其余根层文档成子页
    target2 = _make_leaf(client, headers, pid, None, "另一个目标")
    files2 = {
        f"{folder}/README.md": "README 内容\n".encode(),
        f"{folder}/{folder}.md": f"# {folder}\n同名内容\n".encode(),
        f"{folder}/子章三.md": "子内容\n".encode(),
    }
    r2 = client.post(f"/api/v1/projects/{pid}/import", headers=headers,
                     data={"target_note_id": target2["id"]},
                     files=[("files", (p, c, "text/markdown")) for p, c in files2.items()])
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["matched_target"] is True
    assert b2["target_renamed"] is True
    page = client.get(f"/api/v1/notes/{target2['id']}", headers=headers)
    assert page.status_code == 200
    detail = page.json()
    assert detail["title"] == folder
    texts = [blk.get("content", {}).get("text", "") for blk in (detail.get("blocks") or [])]
    assert any("同名内容" in t for t in texts)


def test_agent_kb_search_tool(monkeypatch):
    """search_knowledge_base：权限门控 + 命中/未命中 + 检索失败提示"""
    from app.services import rag as rag_svc
    from app.services import tools

    # 未登录/无项目上下文 → 明确提示不可用
    out = tools.execute_tool("search_knowledge_base", {"question": "FastAPI 是什么"},
                             {"kb": {"enabled": False}})
    assert "知识库检索暂不可用" in out

    # 指定无权项目 → 拒绝
    out = tools.execute_tool("search_knowledge_base",
                             {"question": "x", "project_id": "proj-other"},
                             {"kb": {"enabled": True, "accessible_project_ids": ["p1"]}})
    assert "无权访问" in out

    def fake_search(question, accessible, top_k=8):
        assert accessible == ["p1"]
        return {"found": True, "sources": [{
            "title": "FastAPI 笔记", "heading_path": "依赖注入",
            "content": "FastAPI 依赖注入通过 Depends 声明参数。",
        }]}

    monkeypatch.setattr(rag_svc, "search_only", fake_search)
    out = tools.execute_tool(
        "search_knowledge_base", {"question": "FastAPI 依赖注入是什么？", "project_id": "p1"},
        {"kb": {"enabled": True, "accessible_project_ids": ["p1", "p2"],
                "project_id": "p1"}},
    )
    assert "命中 1 条" in out
    assert "FastAPI 依赖注入通过 Depends" in out

    # 未命中 → 引导如实说明
    monkeypatch.setattr(rag_svc, "search_only",
                        lambda *a, **k: {"found": False, "sources": [], "context": ""})
    out = tools.execute_tool("search_knowledge_base", {"question": "远古冷门问题"},
                             {"kb": {"enabled": True,
                                     "accessible_project_ids": ["p1"], "project_id": "p1"}})
    assert "未找到与问题相关的内容" in out

    # 检索层失败 → 以文本返回（不抛出）
    def boom(*a, **k):
        raise RuntimeError("未配置 EMBEDDING_MODEL，知识库检索不可用")

    monkeypatch.setattr(rag_svc, "search_only", boom)
    out = tools.execute_tool("search_knowledge_base", {"question": "x"},
                             {"kb": {"enabled": True,
                                     "accessible_project_ids": ["p1"], "project_id": "p1"}})
    assert "知识库检索不可用" in out
