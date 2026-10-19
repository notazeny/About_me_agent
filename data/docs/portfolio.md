# sazeny · AI Agent 开发求职作品集

> **求职方向**：AI Agent 开发工程师（应届）
>
> **一句话**：一条从「工程地基」到「多智能体」、再到「真实上线」和「真实数据」的完整成长弧线——
> 每个项目都能脱稿讲清「为什么这样设计」。

## 演进主线

```
手写 RAG 基础 ──▶ 手写 ReAct 闭环 ──▶ LangGraph 工程化（记忆 / 护栏 / 评测 / 可观测）
                                                       ──▶ 多智能体 + MCP / A2A 协议
                                                       ──▶ 产品化上线（个人 AI 分身网站）
                                                       ──▶ 真实数据应用（求职情报 Agent）
```

前四段证明「**能把一个 agent 做深、让多个 agent 协作**」；后两段证明「**能把它们真的跑起来，
并用到真实数据上**」。

## 项目全景

| 阶段 | 项目 | 一句话 | 关键技术 | 仓库 / 地址 |
|---|---|---|---|---|
| 0 | Async_LLM_Gateway | 并发 + 流式 + 测试的工程地基 | `asyncio.gather` / SSE 重连 / pytest | 本地 |
| 1 | Structured_Output_Tool | 把模型畸形的 JSON 救回来 | 三层管线 + 分层异常兜底 | [gitee](https://gitee.com/sazeny/structured-output-tool) |
| 2 | RAG_Job Search Knowledge Agent | 带引用出处的知识库问答 | 手写 RAG / 混合检索 / rerank / ChromaDB | [github](https://github.com/notazeny/RAG-Job-Search-Knowledge-Agent) |
| 2 | SQL_Data analysis Agent | 自然语言 → SQL 查库 | 工具调用 / 步骤规划 | [gitee](https://gitee.com/sazeny/sql-data-analysis-agent) |
| 3 | ReAct_Agent | 手写 ReAct 闭环 | while 循环 / Parser / 防死循环 | [github](https://github.com/notazeny/-ReAct_Agent) |
| 4-6 | LangGraph_Agent | 单 Agent 的工程完整度 | 记忆 / HITL / 护栏 / 评测 / 可观测 / Docker | [gitee](https://gitee.com/sazeny/LangGraph_Agent) |
| 7 | Multi_Agent | 多 Agent 协作 + 标准协议 | Supervisor-Worker / MCP / A2A | [gitee](https://gitee.com/sazeny/multi_-agent) |
| **8** | **个人 AI 分身网站** | **已上线的产品化应用** | **FastAPI + Vue3 + MySQL + 手写检索 + 语义缓存** | [在线体验](http://8.148.192.49/) ｜ [github](https://github.com/notazeny/About_me_agent) |
| **9** | **Job_Intel_Agent** | **真实数据的求职情报应用** | **多公司采集 / SimHash 去重 / LLM 抽取 / 匹配** | [github](https://github.com/notazeny/Job_Intel_Agent) |

## 已上线：个人 AI 分身网站

**地址**：http://8.148.192.49/ （现在就能打开）

**做了什么**：HR 打开网页，就能和「sazeny 的 AI 分身」做一次初步面试——问项目、问技术栈、
问求职方向。回答基于真实语料，附引用出处，还能点开源文本核对。

**技术栈**：FastAPI + Vue3 + TypeScript + MySQL + SQLAlchemy + ChromaDB + BAAI-BGE +
DeepSeek + Nginx + systemd + GitHub Actions

**关键设计（都能讲清为什么）**：

- **检索内核复用而非重写**：直接复用 RAG 项目的向量 + BM25 + 加权 RRF + reranker，
  只加了业务层。这是「工程沉淀」的体现，不是偷懒。
- **语义缓存只缓存检索、不缓存答案**：检索是纯函数 `question → chunks`，缓存永远安全；
  答案受多轮上下文和随机性影响，缓存会固化一次性转述。
- **启动预热 + `HF_HUB_OFFLINE`**：把模型加载从「第一个访客头上」挪到「部署期间」。
  实测那笔「冷启动 13 秒」有 11 秒是等 HuggingFace 联网检查，纯加载只要 2.5 秒。
- **线上性能**：首字延迟 **34.7s → 25.2s**，重复问题 **~1.4s**（语义缓存命中）。
- **可观测**：请求 ID + 结构化日志 + chat 分段打点（retrieve / first_token / gen / total）。

**回答的问题**：「你能把 AI 应用真的部署上线吗？」——能，现在就能打开验证。

## 真实数据：Job_Intel_Agent

**做了什么**：采集公开招聘数据 → LLM 结构化抽取 → 与简历比对 → 输出「该投哪家 / 我缺什么」。
解决的是求职时人工阅读上百份 JD 效率极低的问题。

**技术栈**：Python + FastAPI + Pydantic + DeepSeek API + httpx + JSONL + pytest

**关键设计**：

- **飞书招聘通用适配器**：一套代码接入 7 家公司（字节、MiniMax、百川、零一万物、面壁、
  智谱、商汤），累计 **1064 条**真实 JD；串行限频 3s + 指数退避 + 原始响应按日归档。
- **业务主键 upsert**：实测发现同一岗位的 `source_id` 会变（正文一字不差、id 不同），
  改用「公司 + 城市集合 + 标题」做主键跨批次 upsert，「假新增」从 35 条降为 0；
  近似去重按主键分桶后，跨城市误杀 13 对 → 0。
- **LLM 抽取**：三层管线（JSON 提取 → 尾逗号修复 → Pydantic 校验）+ 校验失败回灌重试，
  124 条 JD **0 失败**；按内容指纹缓存，重跑零成本。

**回答的问题**：「你做的 AI 应用有真实数据和真实用户吗？」——有，1064 条真实 JD，
用户就是我自己。

## 两个旗舰（技术深度）

### ① LangGraph_Agent —— 单 Agent 的「工程深度」

把「一个 agent 做深」：长短期记忆、HITL 审批、双层注入护栏（直接 + 间接）、
LLM-as-Judge 评测、手写 trace 可观测、Docker + Redis 部署。

**回答的问题**：「你能把一个 agent 做到生产级的工程完整度吗？」——能。

### ② Multi_Agent —— 多 Agent 的「架构广度」

把「多 agent 协作 + 标准协议」落地：Supervisor-Worker 多智能体（脑）+ 手写 MCP Server（手）
+ A2A 协议（嘴），一条消息穿过「嘴 → 脑 → 手」三层。

**回答的问题**：「你懂 2026 面试的区分项吗（多智能体 + MCP + A2A）？」——懂，而且亲手写过。

> 四个旗舰是「同一个人的能力弧线」：单 Agent 的深度 → 多 Agent 的广度 →
> 产品化上线 → 真实数据应用。

## 技能图谱

- **Agent 内核**：ReAct 循环、LangGraph 状态机、Parser 健壮性、防死循环、
  Supervisor-Worker 多智能体、**上下文工程**（读时裁剪 / 摘要缓冲 / 长期记忆分层）
- **检索（RAG）**：分块、BM25、向量检索、混合检索（RRF 融合）、rerank、
  ChromaDB 持久化 + 增量更新
- **协议**：MCP（手写 Server + Client）、A2A（Agent Card + Task 状态机 + SSE）
- **安全与可观测**：提示词注入护栏（直接 / 间接）、工具沙箱白名单、HITL、
  手写 trace、LLM-as-Judge 评测
- **工程**：asyncio、SSE 流式、FastAPI、MySQL、Redis、Docker、Nginx、
  GitHub Actions、pytest（各项目核心链路均覆盖单测）

## 关于我

（简历中详述。）本作品集所有项目均可 clone 运行，各 README 内含架构说明与运行方式；
个人 AI 分身网站为**在线可访问**的真实部署。
