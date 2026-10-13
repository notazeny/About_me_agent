# sazeny · AI Agent 开发求职作品集

> **求职方向**：AI Agent 开发工程师（应届）
>
> **一句话**：一条从「工程地基」到「多智能体 + 标准协议」的完整成长弧线——7 个项目沿 9 阶段学习路线逐步演进，每个都能脱稿讲清「为什么这样设计」。

## 演进主线

```
手写 RAG 基础 ──▶ 手写 ReAct 闭环 ──▶ LangGraph 工程化（记忆 / 护栏 / 评测 / 可观测）
                                                       ──▶ 多智能体 + MCP / A2A 协议
```

前半段证明「**能用一个 agent 把一件事做深**」，后半段证明「**能让多个 agent 用标准协议协作**」。

## 项目全景

| 阶段 | 项目 | 一句话 | 关键技术 | 仓库 |
|---|---|---|---|---|
| 0 | Async_LLM_Gateway | 并发 + 流式 + 测试的工程地基 | `asyncio.gather` / SSE 重连 / pytest | 本地 |
| 1 | Structured_Output_Tool | 把模型畸形的 JSON 救回来 | 三层管线 + 分层异常兜底 | [gitee](https://gitee.com/sazeny/structured-output-tool) |
| 2 | RAG_Job Search Knowledge Agent | 带引用出处的知识库问答 | 手写 RAG / 混合检索 / rerank / ChromaDB | [github](https://github.com/notazeny/RAG-Job-Search-Knowledge-Agent) |
| 2 | SQL_Data analysis Agent | 自然语言 → SQL 查库 | 工具调用 / 步骤规划 | [gitee](https://gitee.com/sazeny/sql-data-analysis-agent) |
| 3 | ReAct_Agent | 手写 ReAct 闭环 | while 循环 / Parser / 防死循环 | [github](https://github.com/notazeny/-ReAct_Agent) |
| 4-6 | LangGraph_Agent | 单 Agent 的工程完整度 | 记忆 / HITL / 护栏 / 评测 / 可观测 / Docker | [gitee](https://gitee.com/sazeny/LangGraph_Agent) |
| 7 | Multi_Agent | 多 Agent 协作 + 标准协议 | Supervisor-Worker / MCP / A2A | [gitee](https://gitee.com/sazeny/multi_-agent) |

## 两个旗舰（简历重点）

### ① LangGraph_Agent —— 单 Agent 的「工程深度」

把「一个 agent 做深」：长短期记忆、HITL 审批、双层注入护栏（直接 + 间接）、LLM-as-Judge 评测、手写 trace 可观测、Docker + Redis 部署。

**回答的问题**：「你能把一个 agent 做到生产级的工程完整度吗？」——能。

### ② Multi_Agent —— 多 Agent 的「架构广度」

把「多 agent 协作 + 标准协议」落地：Supervisor-Worker 多智能体（脑）+ 手写 MCP Server（手）+ A2A 协议（嘴），一条消息穿过「嘴 → 脑 → 手」三层。检索核心复用 RAG 项目的 BM25 + 向量 + RRF。

**回答的问题**：「你懂 2026 面试的区分项吗（多智能体 + MCP + A2A）？」——懂，而且亲手写过。

> 两者是「同一个人的能力弧线」：LangGraph_Agent 的 README 末段指向 Multi_Agent，Multi_Agent 开头写「这是 LangGraph_Agent 的演进」——单 Agent 的深度 → 多 Agent 的广度。

## 技能图谱

- **Agent 内核**：ReAct 循环、LangGraph 状态机、Parser 健壮性、防死循环、Supervisor-Worker 多智能体
- **检索（RAG）**：分块、BM25、向量检索、混合检索（RRF 融合）、rerank、ChromaDB
- **协议**：MCP（手写 Server + Client）、A2A（Agent Card + Task 状态机 + SSE）
- **安全与可观测**：提示词注入护栏（直接 / 间接）、工具沙箱白名单、HITL、手写 trace、评测体系
- **工程**：asyncio、SSE 流式、FastAPI、Docker、Redis、pytest（各项目核心链路均覆盖单测）

## 关于我

（简历中详述。）本作品集所有项目均可 clone 运行，各 README 内含架构说明与运行方式。
