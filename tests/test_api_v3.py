"""v3 新架构 API 集成测试

覆盖：注册引导、RBAC 隔离、笔记/块 CRUD、组织邀请正向授权、
文件 asset 上传读取、slug 解析与关系图。
"""


def _first_org(client, headers):
    resp = client.get("/api/v1/orgs/", headers=headers)
    assert resp.status_code == 200, resp.text
    orgs = resp.json()
    assert orgs, "注册应自动创建个人组织"
    return orgs[0]


def _first_project(client, headers, org_id):
    resp = client.get(f"/api/v1/orgs/{org_id}/projects/", headers=headers)
    assert resp.status_code == 200, resp.text
    projects = resp.json()
    assert projects, "应存在默认项目"
    return projects[0]


def test_register_creates_personal_org_and_project(client, register):
    headers, user = register("boot")
    org = _first_org(client, headers)
    assert org["my_role"] == "owner"
    assert org["owner_id"] is not None

    projects = client.get(f"/api/v1/orgs/{org['id']}/projects/", headers=headers).json()
    assert any(p["name"] == "我的项目" for p in projects)


def test_rbac_isolation_404_not_leak(client, register):
    ha, _ = register("alice")
    hb, _ = register("bob")

    org_a = _first_org(client, ha)
    project_a = _first_project(client, ha, org_a["id"])
    note = client.post(
        f"/api/v1/projects/{project_a['id']}/notes/",
        json={"title": "私密笔记", "icon": "doc"},
        headers=ha,
    )
    assert note.status_code == 200, note.text
    note_id = note.json()["id"]

    # B 看不到 A 的组织与笔记（统一 404，不泄露存在性）
    assert client.get(f"/api/v1/orgs/{org_a['id']}", headers=hb).status_code == 404
    assert client.get(f"/api/v1/notes/{note_id}", headers=hb).status_code == 404
    assert client.get(f"/api/v1/projects/{project_a['id']}", headers=hb).status_code == 404


def test_note_block_crud_and_stats(client, register):
    headers, _ = register("writer")
    org = _first_org(client, headers)
    project = _first_project(client, headers, org["id"])

    note = client.post(
        f"/api/v1/projects/{project['id']}/notes/",
        json={"title": "CRUD 笔记", "icon": "doc"},
        headers=headers,
    ).json()
    nid = note["id"]

    block = client.post(
        f"/api/v1/notes/{nid}/blocks",
        json={"type": "heading", "content": {"level": 2, "text": "3.1 小节"}},
        headers=headers,
    )
    assert block.status_code == 200, block.text
    bid = block.json()["id"]

    upd = client.patch(
        f"/api/v1/blocks/{bid}",
        json={"content": {"text": "3.1 更新后的标题"}},
        headers=headers,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["content"]["text"] == "3.1 更新后的标题"

    detail = client.get(f"/api/v1/notes/{nid}", headers=headers).json()
    assert any(b["type"] == "heading" for b in detail["blocks"])

    stats1 = client.get(f"/api/v1/notes/{nid}/stats", headers=headers).json()
    assert stats1["view_count"] >= 1
    assert stats1["block_count"] == len(detail["blocks"])

    assert client.delete(f"/api/v1/blocks/{bid}", headers=headers).status_code == 200


def test_org_invite_reporter_gains_read_only(client, register):
    ha, ua = register("owner")
    hb, ub = register("guest")
    org = _first_org(client, ha)

    inv = client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"username": ub["username"], "role": "reporter"},
        headers=ha,
    )
    assert inv.status_code == 200, inv.text

    # B 现在能看见组织并可读项目笔记，但不能写
    orgs_b = client.get("/api/v1/orgs/", headers=hb).json()
    assert any(o["id"] == org["id"] for o in orgs_b)
    project = _first_project(client, ha, org["id"])
    tree = client.get(f"/api/v1/projects/{project['id']}/notes/", headers=hb)
    assert tree.status_code == 200

    note = client.post(
        f"/api/v1/projects/{project['id']}/notes/",
        json={"title": "B 尝试创建", "icon": "doc"},
        headers=hb,
    )
    assert note.status_code == 403, note.text


def test_file_asset_upload_and_readback(client, register):
    headers, _ = register("uploader")
    org = _first_org(client, headers)
    project = _first_project(client, headers, org["id"])
    payload = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes-" * 4

    resp = client.post(
        "/api/v1/files/upload",
        data={"project_id": project["id"], "purpose": "asset"},
        files={"file": ("sample.png", payload, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    meta = resp.json()
    assert meta["status"] == "COMPLETED"

    content = client.get(f"/api/v1/files/{meta['id']}/content", headers=headers)
    assert content.status_code == 200
    assert content.content == payload


def test_slug_resolution_and_graph(client, register):
    headers, _ = register("nav")
    org = _first_org(client, headers)
    project = _first_project(client, headers, org["id"])

    note = client.post(
        f"/api/v1/projects/{project['id']}/notes/",
        json={"title": "锚点笔记", "icon": "doc"},
        headers=headers,
    ).json()

    det = client.get(
        f"/api/v1/projects/{project['id']}/notes/by-slug/{note['slug']}",
        headers=headers,
    )
    assert det.status_code == 200 and det.json()["id"] == note["id"]

    graph = client.get(f"/api/v1/projects/{project['id']}/notes/graph", headers=headers)
    assert graph.status_code == 200
    assert "nodes" in graph.json() and "edges" in graph.json()
