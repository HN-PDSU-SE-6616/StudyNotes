"""文件媒体与导入链接集成测试（分类存储/源路径/媒体 token 访问/用户级文件）

- 目录导入：图片资源按 note_image 分类落盘并保留 source_path，内容改写为
  /api/v1/files/{id}/content；跨文档链接改写为 /notes/{slug}；
- 媒体访问：?access_token=（<img> 无请求头场景）与 Authorization 头等价；
- /files/mine：用户级媒体（图标/背景）上传 → 访问 → 列表 → 删除；
- 真实远程 Embedding 连通性（opt-in：RUN_REMOTE_EMBED=1 且已配置时才执行）。
"""
import os

import pytest

from app.services import embedding

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _first_pid(client, headers):
    orgs = client.get("/api/v1/orgs/", headers=headers).json()
    projects = client.get(f"/api/v1/orgs/{orgs[0]['id']}/projects/", headers=headers).json()
    return projects[0]["id"]


def _leaf(client, headers, pid, parent, title):
    return client.post(
        f"/api/v1/projects/{pid}/notes/",
        json={"title": title, "icon": "doc", "parent_id": parent},
        headers=headers,
    ).json()


def _user_id(client, headers) -> int:
    return client.get("/api/v1/users/me/profile", headers=headers).json()["user_id"]


def test_import_image_links_rewritten_and_media_accessible(client, register):
    """目录导入 → 图片资源分类/源路径/URL 改写 + 跨文档链接修复 + 媒体 token 访问"""
    headers, _ = register("media_imp")
    pid = _first_pid(client, headers)
    target = _leaf(client, headers, pid, None, "导入目标")
    folder = "教程"

    files = {
        f"{folder}/README.md": (
            "# 教程\n\n![示意图](image/logo.png)\n\n延伸阅读 [第二章](chapter.md)\n"
        ).encode("utf-8"),
        f"{folder}/chapter.md": "# 第二章\n并发模型。\n".encode("utf-8"),
        f"{folder}/image/logo.png": PNG_BYTES,
    }
    r = client.post(
        f"/api/v1/projects/{pid}/import", headers=headers,
        data={"target_note_id": target["id"]},
        files=[("files", (p, c, "text/markdown")) if p.endswith(".md")
               else ("files", (p, c, "image/png")) for p, c in files.items()],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assets"] >= 1
    assert body["target_renamed"] is True

    tree = client.get(f"/api/v1/projects/{pid}/notes/", headers=headers).json()
    root = next(n for n in tree if n["id"] == target["id"])
    children = {c["title"]: c for c in (root.get("children") or [])}
    assert {"README", "chapter"} <= set(children), children.keys()
    chapter = children["chapter"]

    # README 内容：图片改写为受保护文件 URL，跨文档链接改写为 /notes/{slug}
    readme = client.get(f"/api/v1/notes/{children['README']['id']}", headers=headers)
    assert readme.status_code == 200
    detail = readme.json()
    image_url = ""
    text_blob = []
    for blk in detail.get("blocks") or []:
        c = blk.get("content") or {}
        if blk["type"] == "image":
            image_url = str(c.get("url") or "")
        elif blk["type"] in ("paragraph", "heading"):
            text_blob.append(str(c.get("text") or ""))
    assert image_url.startswith("/api/v1/files/") and image_url.endswith("/content")
    assert f"/notes/{chapter['slug']}" in "\n".join(text_blob)
    # /api/v1/files/{id}/content → 第 4 段为 file_id
    file_id = image_url.split("/")[4]

    # 文件元数据：category=note_image、source_path 保留原始相对路径、按 用户/类型 落盘
    listing = client.get(f"/api/v1/files/list/{pid}", headers=headers).json()
    assert any(m["id"] == file_id for m in listing), (
        "块内 file_id=" + file_id + " 未命中项目文件列表 rows=" +
        str([(m["id"], m["project_id"], m.get("category"), m.get("source_path"),
              m.get("original_name")) for m in listing]))
    meta = next(m for m in listing if m["id"] == file_id)
    assert meta["category"] == "note_image"
    assert meta["source_path"] == f"{folder}/image/logo.png"
    assert meta["storage_key"].startswith(f"{_user_id(client, headers)}/note_image/")

    # 媒体访问：Bearer 头 与 ?access_token= 均可读，字节一致
    resp_hdr = client.get(image_url, headers=headers)
    assert resp_hdr.status_code == 200 and resp_hdr.content == PNG_BYTES
    token = headers["Authorization"].split(" ", 1)[1]
    resp_q = client.get(f"{image_url}?access_token={token}")
    assert resp_q.status_code == 200 and resp_q.content == PNG_BYTES
    # 无任何凭证 → 404（不泄露）
    assert client.get(image_url).status_code == 404


def test_user_media_mine_upload_list_delete(client, register):
    """用户级媒体：/files/mine 上传分类 → 列表 → token 访问 → 删除"""
    headers, _ = register("media_mine")
    r = client.post(
        "/api/v1/files/mine", headers=headers,
        data={"category": "assistant_icon"},
        files={"file": ("pet.png", PNG_BYTES, "image/png")},
    )
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["category"] == "assistant_icon"
    assert meta["project_id"] is None
    assert meta["storage_key"].startswith(f"{meta['owner_id']}/assistant_icon/")

    url = f"/api/v1/files/mine/{meta['id']}/content"
    token = headers["Authorization"].split(" ", 1)[1]
    assert client.get(f"{url}?access_token={token}").status_code == 200

    mine_list = client.get("/api/v1/files/mine", headers=headers).json()
    assert any(m["id"] == meta["id"] for m in mine_list)

    # 他人不可访问（404）
    other_headers, _ = register("media_mine_o")
    assert client.get(f"{url}?access_token={token}", headers=other_headers).status_code == 404

    d = client.delete(f"/api/v1/files/mine/{meta['id']}", headers=headers)
    assert d.status_code == 200
    assert client.get(f"{url}?access_token={token}").status_code == 404


def _remote_embedding_enabled() -> bool:
    if os.environ.get("RUN_REMOTE_EMBED") != "1":
        return False
    return embedding.is_configured()


@pytest.mark.skipif(not _remote_embedding_enabled(),
                    reason="需 RUN_REMOTE_EMBED=1 且 EMBEDDING 已配置")
def test_remote_embedding_service_real_call(client):
    """真实调用容器内 bge-small-zh（TEI /v1）：返回 512 维可归一化向量"""
    from app.services import embedding as emb

    try:
        vectors = emb.embed_texts(["FastAPI 异步请求测试", "Qdrant 向量检索"])
        emb.unload()
    finally:
        emb.unload()
    assert len(vectors) == 2
    for v in vectors:
        assert len(v) == 512
        assert all(isinstance(x, float) for x in v)
        norm = sum(x * x for x in v) ** 0.5
        assert abs(norm - 1.0) < 1e-3  # normalize_embeddings=True
