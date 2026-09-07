"""批量目录导入 → Note 树 集成测试（v2 语义恢复）

覆盖：目录层级成树、图片资源上链并改写 URL、跨文档 md 链接修复、
overwrite=false 幂等跳过、overwrite=true 重建。
"""


def _tree_map(notes):
    """把树转 flat {id: node}，便于断言"""

    def walk(nodes):
        for n in nodes:
            yield n
            for c in (n.get("children") or []):
                yield from walk([c])
            for c in (n.get("linked_children") or []):
                yield from walk([c])

    return {n["id"]: n for n in walk(notes)}


def _first_org_project(client, headers):
    orgs = client.get("/api/v1/orgs/", headers=headers).json()
    projects = client.get(f"/api/v1/orgs/{orgs[0]['id']}/projects/", headers=headers).json()
    return projects[0]["id"]


FILE_SET = {
    "index.md": "# 总览\n\n[Python 环境](python基础/环境.md)\n\n- 概览甲\n- 概览乙\n".encode("utf-8"),
    "python基础/环境.md": (
        "# Python 环境\n\n"
        "1. 安装 Python\n"
        "2. 配置虚拟环境\n"
        "3. 使用 pip\n\n"
        "![logo](./media/logo.png)\n"
    ).encode("utf-8"),
    "python基础/进阶/进阶.md": "# 进阶\n\n> 引用一句话\n".encode("utf-8"),
    "python基础/media/logo.png": b"\x89PNG\r\n\x1a\nfake-png-content",
}


def _multipart_files(file_set):
    return [("files", (name, data, "application/octet-stream")) for name, data in file_set.items()]


def test_directory_import_builds_tree(client, register):
    headers, _user = register("imp_tree")
    pid = _first_org_project(client, headers)

    r = client.post(
        f"/api/v1/projects/{pid}/import",
        files=_multipart_files(FILE_SET),
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root_note_id"]
    assert len(body["created"]) >= 3  # 根 + python基础 + 进阶
    assert body["assets"] >= 1

    # 树形态：python基础 应挂在根下，进阶挂在 python基础 下
    tree = client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json()
    flat = _tree_map(tree)
    root = flat[body["root_note_id"]]
    assert root["title"] == "总览"  # H1 同步标题
    children = root.get("children") or []
    assert len(children) >= 1
    sub_node = flat[children[0]["id"]]
    assert sub_node["title"] == "python基础"
    assert sub_node["parent_id"] == body["root_note_id"]

    # 环境.md 内容：有序列表合并连号 + 图片 URL 已改写为资源
    detail = client.get(f"/api/v1/notes/{sub_node['id']}", headers=headers).json()
    types = [b["type"] for b in detail["blocks"]]
    assert "list" in types and "image" in types
    list_block = next(b for b in detail["blocks"] if b["type"] == "list")
    assert list_block["content"]["ordered"] is True
    assert list_block["content"]["start"] == 1
    texts = [i["text"] for i in list_block["content"]["items"]]
    assert texts == ["安装 Python", "配置虚拟环境", "使用 pip"]
    img_block = next(b for b in detail["blocks"] if b["type"] == "image")
    assert img_block["content"]["url"].startswith("/api/v1/files/")

    # 根 index.md 中跨文档链接已被修复为 /notes/{slug}
    root_detail = client.get(f"/api/v1/notes/{root['id']}", headers=headers).json()
    paras = [b["content"].get("text", "") for b in root_detail["blocks"] if b["type"] == "paragraph"]
    assert any("/notes/" in p for p in paras), paras


def test_reimport_overwrite_semantics(client, register):
    headers, _user = register("imp_ow")
    pid = _first_org_project(client, headers)

    r1 = client.post(f"/api/v1/projects/{pid}/import", files=_multipart_files(FILE_SET), headers=headers)
    assert r1.status_code == 200
    first = r1.json()
    count_before = len(client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json())

    # overwrite=false：整体跳过，不产生重复
    r2 = client.post(f"/api/v1/projects/{pid}/import", files=_multipart_files(FILE_SET), headers=headers)
    assert r2.status_code == 200
    second = r2.json()
    assert len(second["created"]) == 0
    assert len(second["skipped"]) > 0
    assert second["root_note_id"] is None
    count_after = len(client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json())
    assert count_after == count_before

    # overwrite=true：重建相同内容
    r3 = client.post(
        f"/api/v1/projects/{pid}/import",
        files=_multipart_files(FILE_SET),
        data={"overwrite": "true"},
        headers=headers,
    )
    assert r3.status_code == 200
    third = r3.json()
    assert third["root_note_id"] not in (first["root_note_id"], None)
    assert len(third["created"]) >= 3
    count_after_ow = len(client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json())
    # 旧树被清空重建，根笔记数量不增长
    assert count_after_ow == count_before


def test_import_into_target_note(client, register):
    headers, _user = register("imp_tgt")
    pid = _first_org_project(client, headers)

    note = client.post(
        f"/api/v1/projects/{pid}/notes/",
        json={"title": "目标笔记", "icon": "doc"},
        headers=headers,
    ).json()

    small = {"子/一.md": "# 一\n\n正文一行\n".encode("utf-8")}
    r = client.post(
        f"/api/v1/projects/{pid}/import",
        files=[("files", (name, data, "text/markdown")) for name, data in small.items()],
        data={"target_note_id": note["id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["root_note_id"] == note["id"]
    # 子目录笔记挂在目标笔记下
    tree = client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json()
    flat = _tree_map(tree)
    child = next(n for n in flat.values() if n["title"] == "子")
    assert child["parent_id"] == note["id"]
