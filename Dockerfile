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
#
# ★ 先换国内 apt 源。2026-10-20 实测：直连 deb.debian.org 约 481 kB/s，
#   而且下到一半拿到 502 Bad Gateway，构建直接失败。
#   Debian 12+ 用 deb822 格式（sources.list.d/debian.sources），
#   老版本用 /etc/apt/sources.list —— 两处都兼容处理。
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        if [ -f "$f" ]; then \
            sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' "$f"; \
        fi; \
    done; \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 依赖层单独一层：只改代码时不用重装 torch
COPY requirements.txt ./

# ★ 先装 CPU 版 torch，再装其余依赖。
#   PyPI 上 Linux 的 torch 默认包是 CUDA 版，会连带拖进 nvidia-* 十几个包
#   （2-3GB），而这里根本用不上 GPU。2026-10-20 在服务器上实测过这个坑。
#
# ★ 为什么从本地文件装，而不是 `pip install --index-url .../whl/cpu`：
#   实测容器内访问 download.pytorch.org 会被 SSL 中断：
#     SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]'))
#   而同一台机器上的命令行可以正常下载（196MB / 2分15秒）。
#   更坑的是它的**连锁反应**：PyTorch 索引连不上 → pip 从清华找 +cpu 版本
#   （清华没有）→ 转向 sdist 构建 → 报一个完全无关的错：
#     ERROR: Could not find a version that satisfies flit_core<4,>=3.11
#   所以改成「宿主机先下 wheel，构建时只读本地文件」：
#     pip download --no-deps --only-binary=:all: \
#       --platform manylinux_2_28_x86_64 --python-version 3.10 \
#       --implementation cp --abi cp310 -d docker/wheels \
#       "torch==2.14.1+cpu" --index-url https://download.pytorch.org/whl/cpu
#   换机器/换架构时重新跑这条命令即可。wheel 不进 git（见 .gitignore）。
# 用 bind mount 而不是 COPY：wheel 只在build 时可见，**不进入任何镜像层**
# （COPY 进去再 rm 没用——那是两层，196MB 照样留在镜像里）。
# 注意不能加 --no-index：那会把所有索引关掉，连 torch 自己的依赖
# （networkx / sympy / jinja2 ...）也找不到。--find-links 是"额外来源"，
# 常规依赖走默认 PyPI；torch 因为钉了 +cpu，只会从本地 wheel 命中。
#
# ⚠️ 这里**不要**换清华源。2026-10-20 在构建容器内实测：
#     pypi.tuna.tsinghua.edu.cn → 403 Forbidden
#     pypi.org                  → 200
#   宿主机上清华源很快，但容器网络出口不一样，不能想当然。
RUN --mount=type=bind,source=docker/wheels,target=/wheels \
    pip install --no-cache-dir --find-links=/wheels "torch==2.14.1+cpu"

# 主依赖走默认 PyPI（容器内实测 200；清华源在容器里是 403，见上）
RUN pip install --no-cache-dir -r requirements.txt

# 业务代码 + 语料
COPY . .

# 前端产物从构建阶段拿
COPY --from=frontend /build/dist ./frontend/dist

# ⚠️ 这里**故意不设** HF_HUB_OFFLINE=1。
#   模型没有烘进镜像（那会让镜像再大 1.2GB），而是靠 compose 的
#   `model_cache` 卷持久化——**首次启动时卷是空的，必须能联网下载**。
#   设了离线就会像 2026-10-20 服务器上那次一样：
#   报「连不上 hf-mirror」，实际是「缓存不存在」。
#   等缓存卷填满后，可以在 compose 里加 HF_HUB_OFFLINE=1 省掉联网检查。
ENV PYTHONUNBUFFERED=1 \
    HF_ENDPOINT=https://hf-mirror.com

EXPOSE 8000

# 健康检查：容器自己报告「依赖是不是都通了」，而不是只看进程活着
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
