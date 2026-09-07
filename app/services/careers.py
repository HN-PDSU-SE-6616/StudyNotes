"""IT 职位 → 技术栈 预设词典（新用户 onboarding 两步引导数据源）

每项：key=机器值, label=展示名, tags=推荐技术栈候选（可多选 + 自定义）。
推荐画像文本 = label + 所选 tags + 自定义词，用于 Embedding 生成兴趣向量。
"""

CAREER_OPTIONS: list[dict] = [
    {
        "key": "frontend",
        "label": "前端工程师",
        "tags": ["HTML/CSS", "JavaScript", "TypeScript", "Vue 3", "React",
                 "TailwindCSS", "Vite", "小程序", "跨端开发"],
    },
    {
        "key": "backend",
        "label": "后端工程师",
        "tags": ["Python", "FastAPI", "Django", "Flask", "Go", "Java", "Spring Boot",
                 "Node.js", "SQLAlchemy", "PostgreSQL", "MySQL", "Redis", "微服务"],
    },
    {
        "key": "fullstack",
        "label": "全栈工程师",
        "tags": ["JavaScript", "TypeScript", "Vue 3", "React", "Python", "Node.js",
                 "数据库设计", "接口设计", "部署运维"],
    },
    {
        "key": "ai",
        "label": "AI / 机器学习工程师",
        "tags": ["Python", "PyTorch", "TensorFlow", "LangChain", "RAG", "向量数据库",
                 "Prompt Engineering", "NLP", "Agent", "大模型微调", "深度学习"],
    },
    {
        "key": "data",
        "label": "大数据 / 数据分析",
        "tags": ["Python", "SQL", "Spark", "Hadoop", "Hive", "Flink", "Kafka",
                 "Pandas", "数据仓库", "ETL", "数据可视化"],
    },
    {
        "key": "devops",
        "label": "运维 / DevOps / SRE",
        "tags": ["Linux", "Shell", "Docker", "Kubernetes", "CI/CD", "nginx",
                 "监控告警", "云原生", "网络基础"],
    },
    {
        "key": "qa",
        "label": "测试 / 质量保障",
        "tags": ["pytest", "自动化测试", "接口测试", "性能测试", "Selenium",
                 "单元测试", "持续集成", "测试设计"],
    },
    {
        "key": "mobile",
        "label": "移动端工程师",
        "tags": ["Android", "Kotlin", "iOS", "Swift", "Flutter", "React Native",
                 "小程序", "跨端开发", "性能优化"],
    },
    {
        "key": "game",
        "label": "游戏开发",
        "tags": ["Unity", "Unreal", "C#", "C++", "游戏引擎", "图形学", "关卡设计"],
    },
    {
        "key": "security",
        "label": "安全工程师",
        "tags": ["渗透测试", "Web 安全", "加密技术", "漏洞挖掘", "安全运维",
                 "CTF", "等保合规"],
    },
    {
        "key": "pm",
        "label": "产品经理 / 项目",
        "tags": ["需求分析", "产品设计", "原型工具", "项目管理", "数据分析",
                 "敏捷开发", "用户研究"],
    },
    {
        "key": "custom",
        "label": "其他 / 自定义",
        "tags": ["编程基础", "算法与数据结构", "计算机基础", "操作系统", "网络基础",
                 "数据库", "软件工程"],
    },
]


def role_label(key: str) -> str:
    for opt in CAREER_OPTIONS:
        if opt["key"] == key:
            return opt["label"]
    return key


def profile_search_text(job_role: str, job_role_custom: str | None, tech_tags: list[str]) -> str:
    """将画像转成用于 Embedding 的检索文本（中英混合亦可由 BGE 编码）"""
    parts: list[str] = []
    if job_role == "custom" and job_role_custom:
        parts.append(job_role_custom)
    else:
        parts.append(role_label(job_role))
    parts.extend(tag for tag in (tech_tags or []) if str(tag).strip())
    return "；".join(parts) or "通用技术"
