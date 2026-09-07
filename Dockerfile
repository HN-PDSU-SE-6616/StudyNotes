# ============================================================
#   Taot 知识库 v3 — 后端镜像（backend/worker/beat 共用，uv 管理）
#   构建可选 RAG/AI：docker compose build --build-arg ENABLE_AI=1
# ============================================================

FROM ghcr.io/astral-sh/uv:0.12.6 AS uv

# 说明：前端 SPA 由宿主先构建（frontend/dist），直接 COPY 进镜像，避免构建期拉取 node 镜像。
# 如需镜像内自构建前端，恢复以下 stage 并把下方 COPY 改回 COPY --from=frontend-builder ... ：
# FROM node:20-alpine AS frontend-builder
# WORKDIR /app/frontend
# COPY frontend/package*.json ./
# RUN npm ci
# COPY frontend/ .
# RUN npm run build

FROM python:3.12-slim
WORKDIR /app

ARG ENABLE_AI=0

# 运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv 二进制
COPY --from=uv /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/root/.cache/huggingface \
    STORAGE_ROOT=/app/storage

# 按 uv.lock 冻结安装（ENABLE_AI=1 时附带可选 AI 依赖）
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    if [ "$ENABLE_AI" = "1" ]; then \
        uv sync --frozen --no-dev --extra ai; \
    else \
        uv sync --frozen --no-dev; \
    fi

# 后端与迁移
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY wait_services.py /app/wait_services.py
COPY preload_model.py /app/preload_model.py
COPY .env.example ./.env.example

# 前端 SPA（由宿主构建的 frontend/dist 提供）
COPY frontend/dist/ ./frontend/dist/

RUN mkdir -p storage static uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# 默认：启动 API（backend service 会先执行 alembic upgrade head）
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
