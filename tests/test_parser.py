"""解析器单元测试：Markdown / HTML → 规范 Block 列表协议

协议要点：list 块 content={ordered?, task?, start?, items:[{text, checked?, indent?}]}；
相邻同型列表合并多行 items；有序连号由 start 决定（渲染端处理）。
"""
import json

from app.services import parser

LIST = "list"


def _types(blocks):
    return [b["type"] for b in blocks]


def _lists(blocks):
    return [b for b in blocks if b["type"] == LIST]


def test_md_ordered_merge_with_start():
    md = "1. 第一项\n2. 第二项\n3. 第三项\n\n继续正文"
    blocks = parser.parse_document("a.md", md.encode("utf-8"))
    lists = _lists(blocks)
    assert len(lists) == 1
    c = lists[0]["content"]
    assert c["ordered"] is True
    assert c["start"] == 1
    assert [i["text"] for i in c["items"]] == ["第一项", "第二项", "第三项"]
    # 后续正文独立
    assert _types(blocks)[-1] == "paragraph"


def test_md_ordered_start_from_mid():
    md = "5. 续五\n6. 续六"
    blocks = parser.parse_document("a.md", md.encode("utf-8"))
    c = _lists(blocks)[0]["content"]
    assert c["start"] == 5
    assert len(c["items"]) == 2


def test_md_ul_task_split():
    md = "- 甲\n- 乙\n- [x] 完成\n- [ ] 待办\n- 丙"
    lists = _lists(parser.parse_document("a.md", md.encode("utf-8")))
    # 无序(甲/乙) → 任务组(完成/待办) → 无序(丙)
    assert len(lists) == 3
    first, second, third = lists
    assert first["content"]["ordered"] is False and "task" not in first["content"]
    assert [i["text"] for i in first["content"]["items"]] == ["甲", "乙"]
    assert second["content"]["task"] is True
    assert [i["text"] for i in second["content"]["items"]] == ["完成", "待办"]
    assert second["content"]["items"][0]["checked"] is True
    assert second["content"]["items"][1]["checked"] is False
    assert [i["text"] for i in third["content"]["items"]] == ["丙"]


def test_md_nested_indent_children():
    md = "1. 根\n   - 子A\n   - 子B\n2. 第二"
    lists = _lists(parser.parse_document("a.md", md.encode("utf-8")))
    # 根列表(第1项) → 子无序(indent=1) → 第二项(有序 start=2)
    assert lists[0]["content"]["items"][0]["text"] == "根"
    child = lists[1]["content"]
    assert child["ordered"] is False
    assert [i["indent"] for i in child["items"]] == [1, 1]
    assert lists[2]["content"]["start"] == 2
    assert lists[2]["content"]["items"][0]["text"] == "第二"


def test_md_table_escaped_cells():
    md = "| 列A | 列B |\n| --- | --- |\n| a\\|b | c\\*d |"
    blocks = parser.parse_document("a.md", md.encode("utf-8"))
    table = next(b for b in blocks if b["type"] == "table")
    assert table["content"]["headers"] == ["列A", "列B"]
    assert table["content"]["rows"] == [["a|b", "c*d"]]


def test_md_toc_stripped():
    md = (
        "# 文档标题\n\n"
        "## 目录\n\n"
        "- [第一节](#1)\n- [第二节](#2)\n- [第三节](#3)\n\n"
        "## 真实正文\n"
        "1. 有序一\n2. 有序二"
    )
    blocks = parser.parse_document("a.md", md.encode("utf-8"))
    texts = []
    for b in blocks:
        c = b.get("content") or {}
        if b["type"] == "list":
            texts.extend(i.get("text", "") for i in c.get("items", []))
        else:
            texts.append(c.get("text", ""))
    texts = "".join(texts)
    assert "#1" not in texts
    assert "有序一" in texts


def test_md_image_rel_rewrite():
    md = "![logo](./media/logo.png)"
    blocks = parser.parse_document("a.md", md.encode("utf-8"), rel_url_map={
        "media/logo.png": "/api/v1/files/abc/content",
    })
    img = next(b for b in blocks if b["type"] == "image")
    assert img["content"]["url"] == "/api/v1/files/abc/content"
    # 未命中保留原样
    md2 = "![x](../img/a.png)"
    blocks2 = parser.parse_document("a.md", md2.encode("utf-8"), rel_url_map={"other": "/1"})
    img2 = next(b for b in blocks2 if b["type"] == "image")
    assert img2["content"]["url"] == "../img/a.png"


def test_html_heading_table_quote_code():
    html = """<html><body>
<h2>标题</h2>
<table><thead><tr><th>H1</th><th>H2</th></tr></thead><tbody><tr><td>v1</td><td>v2</td></tr></tbody></table>
<blockquote>引用</blockquote>
<pre><code>print(1)</code></pre>
</body></html>"""
    blocks = parser.parse_document("a.html", html.encode("utf-8"))
    types = _types(blocks)
    assert types == ["heading", "table", "quote", "code"]
    code = next(b for b in blocks if b["type"] == "code")
    assert code["content"]["code"] == "print(1)"


def test_html_ol_nested_merged_with_indent():
    html = """<ol>
<li>第一项</li>
<li>第二项<ol><li>嵌套1</li><li>嵌套2</li></ol></li>
<li>第三项</li>
</ol>
<ul><li>甲</li><li>乙</li></ul>"""
    blocks = parser.parse_document("a.html", html.encode("utf-8"))
    lists = _lists(blocks)
    assert len(lists) == 2
    ordered, unordered = lists
    oc = ordered["content"]
    assert oc["ordered"] is True
    # 同型连续项并入一块，嵌套深度用 indent 表达
    assert [i["text"] for i in oc["items"]] == ["第一项", "第二项", "嵌套1", "嵌套2", "第三项"]
    assert [i["indent"] for i in oc["items"]] == [0, 0, 1, 1, 0]
    uc = unordered["content"]
    assert uc["ordered"] is False
    assert [i["text"] for i in uc["items"]] == ["甲", "乙"]


def test_html_image_kept_relative_for_rewrite():
    html = '<img src="media/x.png" alt="x">'
    blocks = parser.parse_document("a.html", html.encode("utf-8"))
    img = next(b for b in blocks if b["type"] == "image")
    assert img["content"]["url"] == "media/x.png"


def test_serializable_json():
    """解析结果必须可直接 JSON 序列化（落库 JSONB）"""
    md = "# 标题\n\n1. 一\n2. 二\n\n| a | b |\n| - | - |\n| 1 | 2 |\n"
    blocks = parser.parse_document("x.md", md.encode("utf-8"))
    dumped = json.dumps(blocks, ensure_ascii=False)
    assert json.loads(dumped) == blocks
