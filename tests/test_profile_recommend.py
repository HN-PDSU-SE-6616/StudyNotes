"""画像（冷启动 onboarding）与推荐权重测试"""
from app.tasks.recommend import _effective_weights


def test_profile_crud(client, register):
    headers, _user = register("prof")

    # options
    options = client.get("/api/v1/users/me/profile/options", headers=headers)
    assert options.status_code == 200
    assert any(o["key"] == "ai" for o in options.json()["options"])

    # 初始为空
    empty = client.get("/api/v1/users/me/profile", headers=headers).json()
    assert empty["job_role"] is None

    # 保存职业 + 技术栈（AI 工程师）
    r = client.put("/api/v1/users/me/profile", headers=headers, json={
        "job_role": "ai",
        "tech_tags": ["Python", "LangChain", "RAG"],
    })
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["job_role"] == "ai"
    assert saved["tech_tags"] == ["Python", "LangChain", "RAG"]

    # 回读一致
    again = client.get("/api/v1/users/me/profile", headers=headers).json()
    assert again["job_role"] == "ai"
    assert again["tech_tags"] == ["Python", "LangChain", "RAG"]

    # 自定义职业
    r2 = client.put("/api/v1/users/me/profile", headers=headers, json={
        "job_role": "custom",
        "job_role_custom": "嵌入式工程师",
        "tech_tags": ["C", "RTOS"],
    })
    assert r2.status_code == 200
    assert r2.json()["job_role_custom"] == "嵌入式工程师"

    # 超限校验
    r3 = client.put("/api/v1/users/me/profile", headers=headers, json={
        "tech_tags": [f"t{i}" for i in range(25)],
    })
    assert r3.status_code == 422


def test_effective_weights_normalize():
    # 画像+行为：原比例
    w = _effective_weights(True, True)
    assert abs(w["wp"] - 0.40) < 1e-6
    assert abs(w["wr"] - 0.25) < 1e-6
    assert abs(w["wv"] - 0.25) < 1e-6
    assert abs(w["wf"] - 0.10) < 1e-6
    assert abs(sum(w.values()) - 1.0) < 1e-6

    # 仅画像（无行为）：read 权重并入 profile → 0.65/0.25/0.10
    w2 = _effective_weights(True, False)
    assert abs(w2["wp"] - 0.65) < 1e-6
    assert w2["wr"] == 0.0
    assert abs(sum(w2.values()) - 1.0) < 1e-6

    # 仅行为（无画像）
    w3 = _effective_weights(False, True)
    assert w3["wp"] == 0.0
    assert abs(w3["wr"] - 0.65) < 1e-6

    # 全无 → 热度为主
    w4 = _effective_weights(False, False)
    assert w4["wr"] == 0.0 and w4["wp"] == 0.0
    assert w4["wv"] > w4["wf"]
    assert abs(sum(w4.values()) - 1.0) < 1e-6
