# ============================================================
# About_Me_Agent 镜像（多阶段）
#
#   阶段 1：node 构建前端 → frontend/dist
#   阶段 2：python 运行后端，把前端产物 COPY 进去
#
# 为什么多阶段：服务器上不需要 node，也不需要 node_modules（86MB）。
# 只把打包后的几十 KB 静态文件带进运行镜像。
#
# ⚠️ 镜像会比较大（sentence-transformers + FlagEmbedding 会拉 torch，
#    约 2GB+）。这是本地跑 BGE embedding / reranker 的代价。
#    如果以后把 rerank 拆成独立服务或改 ONNX，这个镜像能瘦一大圈。
# ============================================================

# ---------- 阶段 1：构建前端 ----------
FROM node:24-slim AS frontend
WORKDIR /build

# 先只拷 package 文件：依赖没变时这一层能命中缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# vue-tsc 类型检查 + vite 打包
RUN npm run build


# ---------- 阶段 2：运行 ----------
FROM python:3.10-slim

# 对齐服务器版本（Ubuntu 22.04 的 venv 是 3.10）。
# 这个项目吃过「CI 用 3.11、服务器装不上」的亏，镜像也别再犯。

WORKDIR /app

# chromadb / pdfplumber 在 slim 镜像里编译时需要这些
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 依赖层单独一层：只改代码时不用重装 torch
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 业务代码 + 语料
COPY . .

# 前端产物从构建阶段拿
COPY --from=frontend /build/dist ./frontend/dist

# HF_HUB_OFFLINE=1：模型已经烘进镜像缓存时，别再联网检查
# （实测那一步会白等 11 秒，见 learn+/学习进度.md）
ENV PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1

EXPOSE 8000

# 健康检查：容器自己报告「依赖是不是都通了」，而不是只看进程活着
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
