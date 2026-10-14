"""pytest 全局夹具：让测试跑在独立的 SQLite 上——不碰真 MySQL、不调真 LLM。

★ 关键顺序：必须在 import app 之前设好环境变量。
  因为 `src/config.py` 在 **import 那一刻** 就读环境变量把 DATABASE_URL 定死，
  `src/session_store.py` 又在 import 那一刻 `create_engine`。
  一旦 app 被 import 过，再改环境变量就没用了。
"""
import os
import sys
from pathlib import Path

# ---- 1) 先设环境变量（必须早于任何 src / app 的 import）----
_TEST_DB = Path(__file__).resolve().parent / "test_aboutme.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"   # 走 SQLite，不连 MySQL
os.environ["JWT_SECRET_KEY"] = "test-only-secret-not-for-production"
os.environ["DEEPSEEK_API_KEY"] = "test-dummy-key"                 # 测试不真调 LLM
# client 夹具不用 `with TestClient(app)`，lifespan 本来就不跑；这里是双保险——
# 万一以后有人改成 with 写法，也不会让测试去加载 bge/reranker 模型。
os.environ["WARMUP_ON_STARTUP"] = "0"

# ---- 2) 让 `import app` 能找到项目根下的 app.py ----
# pytest 从 tests/ 收集用例时，sys.path 里不一定有项目根目录。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    """整个测试会话开始前建表；结束后释放连接、删掉测试库文件。"""
    from src import session_store
    session_store.init_db()
    yield
    session_store.engine.dispose()
    _TEST_DB.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _clean_tables():
    """每个用例前清空三张表，保证用例之间互不污染。"""
    from sqlalchemy import delete

    from src import session_store

    with session_store._session() as s:
        s.execute(delete(session_store.Message))
        s.execute(delete(session_store.Session))
        s.execute(delete(session_store.User))
    yield


@pytest.fixture
def client():
    """FastAPI 测试客户端。

    TestClient 不起真服务器、不占端口，直接把请求交给 ASGI app 处理。
    这里不用 `with TestClient(app)`，所以 app 的 lifespan 不会跑——
    建表由上面的 _prepare_db 负责，效果一样。
    """
    from fastapi.testclient import TestClient

    from app import app

    return TestClient(app)
