```text
blog/
├── app/
│   ├── __init__.py
│   ├── main.py          # 入口
│   ├── database.py      # 数据库连接
│   ├── models.py        # 数据模型
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── notes.py     # 笔记 CRUD 接口
│   │   └── convert.py   # MD 转 HTML 接口
│   └── utils/
│       ├── __init__.py
│       └── markdown.py  # MD 转换工具
├── static/              # 静态资源
├── templates/           # HTML 模板
├── uploads/             # 上传的 MD 文件
├── requirements.txt
└── README.md
```
