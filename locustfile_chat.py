"""About_Me_Agent 压测脚本（第二阶段）：打 /chat，观察 LLM + 检索 + 限流。

和 locustfile.py（压 /api/links 的吞吐基线）是**两个不同的测量目标**：
    · /api/links  → web 层能扛多少 QPS（无鉴权、无模型）
    · /chat       → 一次真实问答要多久、并发时怎么退化

★ 三个必须避开的坑（2026-10-24 实测总结）：

  1) **应用层限流**：config.RATE_LIMIT_PER_MINUTE = 10，每 IP 每分钟 10 次提问。
     不限速地压，几秒内全是 429，测到的是限流不是性能。
     → 用 wait_time 把节奏压到每分钟 10 次以下。

  2) **语义缓存命中**：同一个问题第二次开始会命中缓存（~1.4s），
     根本走不到 rerank。旧版脚本固定问「介绍一下你自己」，压出来的是缓存路径。
     → 每个用户从题库里随机取不同的问题，并保证题库够大、不至于重复。

  3) **SSE 流式**：locust 记的响应时间是「整个流读完」，
     不等于用户感知的首字延迟。
     → 首字延迟要看服务端日志里的 first_token_ms（见文末命令）。

运行（服务器上）：
    /tmp/locustenv/bin/locust -f /tmp/locustfile_chat.py --headless \
        -u 2 -r 1 -t 3m --host http://127.0.0.1:8000

看首字延迟（另开一个窗口，跑完再看）：
    journalctl -u about_me_agent --since "10 min ago" --no-pager \
      | grep 'chat.stages' | tail -20
"""
import random

from locust import HttpUser, between, task

# 题库：覆盖不同主题，避免语义缓存命中（阈值 0.95，主题不同就不会命中）
QUESTIONS = [
    "介绍一下你自己",
    "你最熟悉的技术栈是什么",
    "讲一下你的 RAG 项目是怎么做的",
    "你为什么手写 RAG 而不用 LangChain",
    "你在项目里遇到的最大困难是什么",
    "你是怎么解决模型幻觉问题的",
    "说说你对上下文工程的理解",
    "你的检索链路为什么用 RRF 而不是加权求和",
    "你做过哪些性能优化",
    "你的项目怎么测试的",
    "为什么选择 AI Agent 方向发展",
    "你未来三年的规划是什么",
    "你觉得这个岗位最需要什么能力",
    "讲一个你从零到一完成的项目",
    "你的网站现在线上跑得怎么样",
]


class ChatUser(HttpUser):
    # 每 IP 每分钟限 10 次提问；2 个用户 × 每 25-35 秒一次 ≈ 4 次/分钟，安全区内。
    # 想压更高并发，得先临时调大 RATE_LIMIT_PER_MINUTE（会改变被测对象，需注明）。
    wait_time = between(25, 35)

    def on_start(self):
        # 只登录、不注册：并发注册会撞唯一索引（上一版压测打出来的竞态）
        r = self.client.post(
            "/login",
            json={"username": "loadtest", "password": "loadtest123"},
        )
        self.token = r.json()["token"]
        r = self.client.post(
            "/sessions",
            headers={"Authorization": "Bearer " + self.token},
        )
        self.session_id = r.json()["id"]

    @task
    def chat(self):
        question = random.choice(QUESTIONS)
        self.client.post(
            f"/sessions/{self.session_id}/chat",
            json={"question": question},
            headers={"Authorization": "Bearer " + self.token},
        )
