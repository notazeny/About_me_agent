"""About_Me_Agent 压测脚本（Locust）。

第一阶段：测 /api/links（公开、无鉴权、最快），建立「web 层基线」。
后面再逐步加 /sessions（鉴权）和 /chat（LLM + 限流）任务。

运行（headless）：
  locust -f locustfile.py --headless -u 10 -r 5 -t 30s --host http://localhost:8000
    -u 10   = 10 个虚拟用户
    -r 5    = 每秒启动 5 个
    -t 30s  = 跑 30 秒
"""
from locust import HttpUser, constant, task


class WebsiteUser(HttpUser):
    # wait_time = between(1, 2)  → 模拟「真实用户想 1-2 秒」，测的是「能不能扛住 N 个用户」
    # wait_time = constant(0)    → 一返回就立刻再发，测的是「系统吞吐极限」
    wait_time = constant(0)

    @task
    def get_links(self):
        self.client.get("/api/links")
