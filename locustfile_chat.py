"""About_Me_Agent 压测脚本（第二阶段）：打 /chat，观察 LLM + 限流瓶颈。

先手动注册 loadtest 用户（curl 或脚本），这里 on_start 只登录、不注册，
避免并发注册撞唯一索引（上一版压测打出来的那个竞态）。

运行：
  locust -f locustfile_chat.py --headless -u 5 -r 5 -t 30s --host http://localhost:8000
"""
from locust import HttpUser, task, constant


class ChatUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        r = self.client.post("/login", json={"username": "loadtest", "password": "loadtest123"})
        self.token = r.json()["token"]
        r = self.client.post("/sessions", headers={"Authorization": "Bearer " + self.token})
        self.session_id = r.json()["id"]

    @task
    def chat(self):
        self.client.post(
            f"/sessions/{self.session_id}/chat",
            json={"question": "介绍一下你自己"},
            headers={"Authorization": "Bearer " + self.token},
        )
