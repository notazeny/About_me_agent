# About_Me_Agent —— sazeny 的 AI 分身

> HR 打开网页，就能和「sazeny 的 AI 分身」做一次初步面试：问项目、问技术栈、问求职方向。分身基于 sazeny 的真实语料回答，附引用出处，还能点开看 sazeny 的原话源文本。

线上地址：<http://8.148.192.49/>

## 它解决了什么

简历是静态的，HR 的问题是有靶子的。About_Me_Agent 把「我是谁、做过什么、会什么」蒸馏成**可检索的非隐私语料**，让 HR 像和真人聊天一样提问——一次证明 **RAG + 向量检索 + 多会话 + 部署 + 可观测** 五个能力。

## 功能

- **知识问答**：检索非隐私语料（简历 / 作品集 / 项目 README），DeepSeek 生成带引用出处的回答。
- **面试分身**：按 sazeny 的原话润色成更专业的表达（不捏造、不夸大、忠于原意），网页明示是 AI 分身。
- **诚实兜底**：没准备的问题老实说「建议当面聊」，绝不编造。
- **多用户多会话**：注册 / 登录（JWT），每个用户的数据互相隔离；会话可新建 / 切换 / 删除。
- **源文本按钮**：每条回答可点开查看 sazeny 的原话源文本。
- **语义缓存**：重复或同义问题直接返回缓存结果，跳过 rerank（线上实测 ~1.4 秒 vs 冷启动 25 秒）。

## 技术栈

| 维度 | 选型 |
|---|---|
| 检索 | 手写 RAG：BM25 + 向量 + 加权 RRF 融合 + 交叉编码器 rerank |
| Embedding | 本地 `BAAI/bge-small-zh-v1.5` |
| 向量库 | ChromaDB（持久化 + md5 指纹增量更新） |
| 生成 | DeepSeek `deepseek-chat`（aiohttp 流式，SSE 推到前端） |
| 存储 | MySQL 8 + SQLAlchemy ORM（用户 / 会话 / 消息三表，用户隔离） |
| 后端 | FastAPI + uvicorn |
| 前端 | Vue3 + TypeScript + Pinia + axios（SSE 流式 + markdown 渲染） |
| 鉴权 | JWT（24h）+ bcrypt 慢哈希 + 按 IP 限流 |
| 部署 | Nginx 反代 + systemd（专用非 root 用户）；另有 Dockerfile + compose |
| CI/CD | GitHub Actions：ruff → pytest（真 MySQL service）→ 构建前端 → rsync → 健康检查 |
| 静态检查 | ruff（规则集见 `pyproject.toml`） |

## 架构（数据流）

```
HR 提问 → 前端(Vue3) → Nginx → FastAPI
                                ├─ 鉴权：JWT → 用户隔离
                                ├─ 检索：语义缓存 →(未命中)→ BM25 + 向量
                                │        → 加权 RRF → rerank → top-k
                                ├─ 生成：persona system prompt + 片段 → DeepSeek（流式）
                                └─ 存储：MySQL 存会话 / 消息 / 源文本
                回答 + 引用 + 源文本 → SSE 逐字返回 → 前端
```

**重依赖是懒加载的**：`import app` 不会拉起 torch / chromadb，
只有真的走到预热、chat 或 `/healthz` 时才加载（实测 `import app` 6.0s → 0.6s）。
这也是 CI 能在几十秒内装完依赖的前提——见 `requirements-rag.txt` 的说明。

## 运行

```bash
# 两份都要装：rag 那份是 chat 接口用的（约 1.5GB，torch 为主）
pip install -r requirements.txt -r requirements-rag.txt
cp .env.example .env                 # 填入 DEEPSEEK_API_KEY 等
python scripts/index_docs.py         # 建库：语料 → 分块 → 向量
python -m uvicorn app:app --reload   # 启动，浏览器开 http://127.0.0.1:8000
```

只跑测试（不需要重依赖）：

```bash
pip install -r requirements-dev.txt
pytest tests/ -q                     # 36 例，约 10 秒
ruff check .
```

## 部署

生产环境当前是 **Nginx + systemd**：

- `deploy/nginx/aboutme.conf`：反代到 `127.0.0.1:8000`，SSE 关闭缓冲
- `deploy/systemd/about_me_agent.service`：`User=aboutme`（非 root）、`HF_HUB_OFFLINE=1`
- `deploy/README.md`：完整操作手册

Docker（本地已验证，线上未切换）：

```bash
docker compose up -d                 # app + mysql，首次会下载模型到 model_cache 卷
```

## 目录结构

```
About_Me_Agent/
├── app.py                    # FastAPI 入口（鉴权/会话/问答/健康检查）
├── src/
│   ├── config.py             # 配置（路径/检索参数/DeepSeek/persona 插槽）
│   ├── auth.py               # JWT 签发校验 + bcrypt
│   ├── session_store.py      # MySQL 存储（用户/会话/消息）+ SQLAlchemy
│   ├── errors.py             # 统一错误码
│   ├── observability.py      # 请求 ID + 结构化日志 + 分段打点
│   ├── document_loader.py    # 文档读取 + 分块（.txt/.md/.pdf/.docx）
│   ├── embedder.py           # 本地 BGE 向量化
│   ├── bm25.py               # 手写 BM25（jieba 分词）
│   ├── vector_store.py       # ChromaDB 持久化 + 增量同步
│   ├── reranker.py           # bge-reranker 交叉编码精排
│   ├── fusion.py             # 加权 RRF（纯函数，零重依赖）
│   ├── hybrid_retriever.py   # 混合检索（向量+BM25 → RRF → rerank）
│   ├── semantic_cache.py     # 语义缓存（只缓存检索结果，不缓存答案）
│   ├── generator.py          # 提示词组装 + DeepSeek 流式生成
│   └── persona.py            # 分身插槽（风格画像 → system prompt）
├── frontend/                 # Vue3 + TS 前端源码（构建产物由 Nginx 托管）
├── static/index.html         # 后端兜底页（Nginx 未接管时的降级）
├── scripts/index_docs.py     # 建库脚本
├── tests/                    # 36 例（接口 / 纯函数 / 语义缓存）
├── deploy/                   # Nginx / systemd / 部署手册
├── Dockerfile                # 多阶段（node 构建前端 → python 运行）
├── docker-compose.yml        # app + MySQL 8
├── requirements.txt          # 轻依赖（web/db/auth/numpy）
├── requirements-rag.txt      # 重依赖（模型 + 向量库）
└── requirements-dev.txt      # 测试与静态检查（CI 用这份）
```

## 为什么这样设计（面试叙事）

- **为什么手写 RAG 不引框架**：理解原理后换框架只是换 API 调用，先手写、再懂框架。
- **为什么用 MySQL 而不是 SQLite**：多用户并发、用户隔离、事务与索引；SQLite 只用于本地测试。
- **为什么只缓存检索结果、不缓存答案**：检索是纯函数 `question → chunks`，缓存永远安全；答案受多轮上下文和随机性影响，缓存会固化一次性转述。
- **为什么重依赖懒加载**：接口测试用不到 torch，`import app` 就不该为它付账——这也是 CI 从 2 分钟降到几十秒的根因。
- **为什么测试里有 2 个 `importorskip`**：那两个用例测的是检索链路集成，缺 rag 依赖时跳过而不是失败；完整链路在本地和服务器上跑。
- **为什么 `weighted_rrf` 单独放 `fusion.py`**：一行公式不该以 1.5GB 依赖为代价才能被测到。

## 线上实测

| 指标 | 数值 | 说明 |
|---|---|---|
| 首字延迟（部署前） | 34.7 s | 含 ~13 s HuggingFace 联网检查 |
| 首字延迟（预热后） | 25.2 s | rerank 占大头 |
| 语义缓存命中 | ~1.4 s | `retrieve_ms` 59 ms |
| 启动预热 | 7.7 s | bm25 0.85 / embedder 0.61 / reranker 6.12 |
| `/api/links` 压测 | **254 RPS / P95 44ms** | 2 核服务器，locust 与服务同机抢 CPU（保守值），0 失败 |
| Nginx IP 限流 | 10 r/s（突发 20） | 压测中 98% 请求被 503 拒绝——**限流按设计生效** |
| `/chat` 缓存命中 | 检索 48-58ms / 端到端 1.3-3.6s | 2 核服务器，2 用户 |
| `/chat` 未命中（2 并发） | 检索 29-33s / 端到端 31-40s | 单用户时约 20s——**并发 2 就翻倍，CPU 是硬约束** |
| 测试 | 36 例 | 约 10 秒 |
