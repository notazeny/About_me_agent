# About_Me_Agent —— sazeny 的 AI 分身

> HR 打开网页，就能和「sazeny 的 AI 分身」做一次初步面试：问项目、问技术栈、问求职方向。分身基于 sazeny 的真实语料回答，附引用出处，还能点开看 sazeny 的原话源文本。

## 它解决了什么

简历是静态的，HR 的问题是有靶子的。About_Me_Agent 把「我是谁、做过什么、会什么」蒸馏成**可检索的非隐私语料**，让 HR 像和真人聊天一样提问——一次证明 **RAG + 向量检索 + 多会话 + agent + 部署** 五个能力。

## 功能

- **知识问答**：检索非隐私语料（简历 / 作品集 / 项目 README），DeepSeek 生成带引用出处的回答。
- **面试分身**：按 sazeny 的原话润色成更专业的表达（不捏造、不夸大、忠于原意），网页明示是 AI 分身。
- **诚实兜底**：没准备的问题老实说「建议当面聊」，绝不编造。
- **多会话**：像网页版大模型——会话列表可新建 / 切换 / 删除，SQLite 持久化。
- **源文本按钮**：每条回答可点开查看 sazeny 的原话源文本。

## 技术栈

| 维度 | 选型 |
|---|---|
| 检索 | 手写 RAG：BM25 + 向量 + RRF 融合 + rerank |
| Embedding | 本地 `BAAI/bge-small-zh-v1.5` |
| 向量库 | ChromaDB（持久化） |
| 生成 | DeepSeek `deepseek-chat`（aiohttp 流式） |
| 会话存储 | SQLite（sessions + messages 两表，外键级联删除，WAL） |
| 后端 | FastAPI + uvicorn |
| 前端 | 原生 HTML/CSS/JS（含轻量 markdown 渲染） |

## 架构（数据流）

```
HR 提问 → 前端 → FastAPI
                  ├─ 检索：BM25 + 向量 → RRF 融合 → rerank → top-k
                  ├─ 生成：persona system prompt + 资料片段 → DeepSeek
                  └─ 存储：SQLite 存会话与消息（含源文本）
                  回答 + 引用 + 源文本 → 前端
```

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env                 # 填入 DEEPSEEK_API_KEY
python scripts/index_docs.py         # 建库：语料 → 分块 → 向量
python -m uvicorn app:app --reload   # 启动，浏览器开 http://127.0.0.1:8000
```

## 目录结构

```
About_Me_Agent/
├── app.py                  # FastAPI 入口（会话 CRUD + 问答 + 导航信息）
├── src/
│   ├── config.py           # 配置（路径/检索参数/DeepSeek/persona 插槽）
│   ├── document_loader.py  # 文档读取 + 分块（.txt/.md/.pdf/.docx）
│   ├── embedder.py         # 本地 BGE 向量化
│   ├── bm25.py             # 手写 BM25（jieba 分词）
│   ├── vector_store.py     # ChromaDB 持久化 + 增量同步
│   ├── reranker.py         # bge-reranker 交叉编码精排
│   ├── hybrid_retriever.py # 混合检索（向量+BM25 → RRF → rerank）
│   ├── generator.py        # 提示词组装 + DeepSeek 流式生成
│   ├── persona.py          # 分身插槽（风格画像 → system prompt）
│   └── session_store.py    # SQLite 多会话存储
├── static/index.html       # 前端（原生 HTML/CSS/JS）
├── scripts/index_docs.py   # 建库脚本
└── data/
    ├── docs/               # 语料（简历/portfolio/README/persona_qa）
    └── persona/            # 风格画像等分身插槽
```

## 为什么这样设计（面试叙事）

- **为什么手写 RAG 不引框架**：理解原理后换框架只是换 API 调用，先手写、再懂框架。
- **为什么用 SQLite 存会话而不是 JSON**：要支持多 HR 并发访问、按更新时间排序、搜索、事务稳定。
- **为什么检索核心复用而非重写**：RAG 项目的检索核心经过测试验证，复用体现「工程沉淀」；同时 `config` 用相对路径定位，复制即用。
