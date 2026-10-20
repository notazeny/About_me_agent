"""接口冒烟测试：验证 stage 1 改造的核心契约还活着。

覆盖范围（都是「秒级、不加载模型」的）：
  - 导航接口
  - 注册 / 登录 / 密码错
  - JWT 鉴权（缺 token / token 无效）
  - 统一错误码
  - 会话 CRUD + 分页
  - 用户隔离（A 看不到 B 的会话）

不覆盖：RAG 检索质量（要加载 bge 模型，属于「质量回归」，
       该走单独的 nightly 流水线，见 learn+/工程化改进待办.md）。
"""

PW = "pw123456"


def _auth(client, username="alice") -> dict:
    """注册 + 登录，返回可直接用的 Authorization 头。"""
    client.post("/register", json={"username": username, "password": PW})
    token = client.post("/login", json={"username": username, "password": PW}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------- 导航 ----------------

def test_links_ok(client):
    r = client.get("/api/links")
    assert r.status_code == 200
    body = r.json()
    assert "github" in body and "gitee" in body


# ---------------- 注册 ----------------

def test_register_ok(client):
    r = client.post("/register", json={"username": "alice", "password": PW})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    assert "id" in r.json()


def test_register_duplicate_returns_40002(client):
    client.post("/register", json={"username": "alice", "password": PW})
    r = client.post("/register", json={"username": "alice", "password": "another"})
    assert r.status_code == 400
    assert r.json()["code"] == 40002          # 用户名已存在


# ---------------- 登录 ----------------

def test_login_ok_returns_token(client):
    client.post("/register", json={"username": "alice", "password": PW})
    r = client.post("/login", json={"username": "alice", "password": PW})
    assert r.status_code == 200
    assert r.json()["token"]                  # 签发了 JWT


def test_login_wrong_password_returns_40103(client):
    client.post("/register", json={"username": "alice", "password": PW})
    r = client.post("/login", json={"username": "alice", "password": "WRONG"})
    assert r.status_code == 401
    assert r.json()["code"] == 40103


def test_login_unknown_user_same_error(client):
    """用户名不存在和密码错必须返回同样的错误码——不泄露「这个用户名存不存在」。"""
    r = client.post("/login", json={"username": "nobody", "password": PW})
    assert r.status_code == 401
    assert r.json()["code"] == 40103


# ---------------- 鉴权 ----------------

def test_sessions_without_token_returns_40101(client):
    r = client.get("/sessions")
    assert r.status_code == 401
    assert r.json()["code"] == 40101          # 未登录


def test_invalid_token_returns_40102(client):
    r = client.get("/sessions", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
    assert r.json()["code"] == 40102          # token 无效


# ---------------- 会话 CRUD ----------------

def test_session_create_get_delete(client):
    h = _auth(client)
    sid = client.post("/sessions", headers=h).json()["id"]

    got = client.get(f"/sessions/{sid}", headers=h)
    assert got.status_code == 200
    assert got.json()["messages"] == []       # 新会话没有消息

    assert client.delete(f"/sessions/{sid}", headers=h).json() == {"ok": True}
    assert client.get(f"/sessions/{sid}", headers=h).status_code == 404


def test_list_sessions_pagination_fields(client):
    h = _auth(client)
    for _ in range(3):
        client.post("/sessions", headers=h)

    body = client.get("/sessions?offset=0&limit=2", headers=h).json()
    assert body["total"] == 3                 # 总数不受 limit 影响
    assert len(body["items"]) == 2            # 本页条数受 limit 限制
    assert body["offset"] == 0 and body["limit"] == 2


def test_unknown_session_returns_40401(client):
    h = _auth(client)
    r = client.get("/sessions/does-not-exist", headers=h)
    assert r.status_code == 404
    assert r.json()["code"] == 40401


# ---------------- 用户隔离（stage 1 的核心产出）----------------

def test_users_cannot_see_each_other(client):
    ha = _auth(client, "alice")
    hb = _auth(client, "bob")
    sid = client.post("/sessions", headers=ha).json()["id"]

    # bob 既看不到、也删不掉 alice 的会话
    assert client.get(f"/sessions/{sid}", headers=hb).status_code == 404
    assert client.delete(f"/sessions/{sid}", headers=hb).status_code == 404
    # bob 的会话列表是空的；alice 的还在
    assert client.get("/sessions", headers=hb).json()["total"] == 0
    assert client.get("/sessions", headers=ha).json()["total"] == 1


# ---------------- 可观测：请求 ID ----------------

def test_response_carries_request_id(client):
    """每个响应都带 X-Request-ID —— 排查线上问题时靠它串起整条请求。"""
    r = client.get("/api/links")
    assert r.headers.get("X-Request-ID")


def test_upstream_request_id_is_reused(client):
    """上游带了 X-Request-ID 就沿用，不自己生成。

    这样一条请求跨 Nginx / 后端时 ID 连贯（链路追踪的雏形），
    也能让前端把 ID 显示给用户。
    """
    r = client.get("/api/links", headers={"X-Request-ID": "trace-abc-001"})
    assert r.headers["X-Request-ID"] == "trace-abc-001"


# ---------------- 健康检查 ----------------

def test_healthz_reports_dependency_checks(client):
    """/healthz 要逐项报告依赖状态，而不是笼统地说「我还活着」。

    测试环境用 SQLite（一定通），向量库可能不存在 —— 所以整体状态
    可能是 200 也可能是 503，但 **db 必须为 True**、结构必须齐全。
    """
    r = client.get("/healthz")
    body = r.json()
    assert r.status_code in (200, 503)
    assert body["checks"]["db"] is True
    assert "vector_store" in body["checks"]
    assert body["status"] in ("ok", "unhealthy")
