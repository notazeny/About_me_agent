"""About_Me_Agent —— FastAPI 入口：sazeny 的 AI 分身（HR 网页面试）。

运行：uvicorn app:app --reload
"""
import json
import time
import threading
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import auth, config, session_store
from src.errors import APIError, register_error_handlers
from src.generator import build_prompt, generate_answer_stream, should_refuse
from src.hybrid_retriever import retrieve_with_rerank
from src.observability import AccessLogMiddleware
from src.vector_store import count_docs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    session_store.init_db()   # 建表（幂等）
    yield


app = FastAPI(title="About_Me_Agent", lifespan=lifespan)
register_error_handlers(app)   # 统一错误码响应

# CORS：放行前端开发服务器（Vite :5173），否则浏览器拦截跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可观测：请求 ID + 结构化访问日志。
# 最后注册 = 最外层 —— 这样它看到的是经过 CORS 等处理后的最终响应。
app.add_middleware(AccessLogMiddleware)


class ChatRequest(BaseModel):
    question: str


class AuthRequest(BaseModel):
    username: str
    password: str


# ---------- 限流（防刷：内存滑动窗口，单 worker 足够） ----------
_rate_log: dict = defaultdict(deque)
_rate_lock = threading.Lock()


def _check_rate(ip: str) -> bool:
    """每 IP 每分钟 / 每天限流。返回 True=放行。"""
    now = time.time()
    with _rate_lock:
        q = _rate_log[ip]
        while q and now - q[0] > 86400:      # 清 24h 前的
            q.popleft()
        minute = sum(1 for t in q if now - t < 60)
        if minute >= config.RATE_LIMIT_PER_MINUTE or len(q) >= config.RATE_LIMIT_PER_DAY:
            return False
        q.append(now)
        return True


# ---------- 注册 / 登录 ----------
@app.post("/register", tags=["auth"])
def register(body: AuthRequest):
    try:
        return auth.register(body.username, body.password)
    except ValueError as e:
        raise APIError(40002, str(e), 400)   # 40002 = 用户名已存在


@app.post("/login", tags=["auth"])
def login(body: AuthRequest):
    try:
        return auth.login(body.username, body.password)
    except ValueError as e:
        raise APIError(40103, str(e), 401)   # 40103 = 用户名或密码错误


# ---------- 会话 ----------
@app.post("/sessions", tags=["sessions"])
def create_session(user: dict = Depends(auth.get_current_user)):
    return session_store.create_session(user["id"])


@app.get("/sessions", tags=["sessions"])
def list_sessions(user: dict = Depends(auth.get_current_user), offset: int = 0, limit: int = 20):
    return session_store.list_sessions(user["id"], offset=offset, limit=limit)


@app.get("/sessions/{session_id}", tags=["sessions"])
def get_session(session_id: str, user: dict = Depends(auth.get_current_user)):
    s = session_store.get_session(session_id, user["id"])
    if s is None:
        raise APIError(40401, "会话不存在", 404)
    s["messages"] = session_store.get_messages(session_id)
    return s


@app.delete("/sessions/{session_id}", tags=["sessions"])
def delete_session(session_id: str, user: dict = Depends(auth.get_current_user)):
    if not session_store.delete_session(session_id, user["id"]):
        raise APIError(40401, "会话不存在", 404)
    return {"ok": True}


# ---------- 问答（SSE 流式） ----------
@app.post("/sessions/{session_id}/chat", tags=["sessions"])
def chat(session_id: str, body: ChatRequest, request: Request, user: dict = Depends(auth.get_current_user)):
    if session_store.get_session(session_id, user["id"]) is None:
        raise APIError(40401, "会话不存在", 404)
    if not _check_rate(request.client.host):
        raise APIError(42901, "请求太频繁，请稍后再试", 429)
    question = body.question.strip()
    if not question:
        raise APIError(40001, "问题不能为空", 400)

    history = session_store.get_messages(session_id)   # 本轮之前的对话
    session_store.add_message(session_id, "user", question)

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def generate():
        if count_docs() == 0:
            answer = "语料还没索引，请先运行 scripts/index_docs.py 建库。"
            yield sse({"delta": answer})
            session_store.add_message(session_id, "assistant", answer, sources=[])
            yield sse({"sources": [], "done": True})
            return

        chunks = retrieve_with_rerank(question)
        if should_refuse(chunks):
            answer = "这个问题我还没准备好，建议当面和 sazeny 聊。"
            yield sse({"delta": answer})
            session_store.add_message(session_id, "assistant", answer, sources=[])
            yield sse({"sources": [], "done": True})
            return

        prompt = build_prompt(question, chunks, history=history)
        parts = []
        for piece in generate_answer_stream(prompt):
            parts.append(piece)
            yield sse({"delta": piece})
        answer = "".join(parts)
        sources = [{"source": c["source"], "text": c["text"]} for c in chunks]
        session_store.add_message(session_id, "assistant", answer, sources=sources)
        yield sse({"sources": sources, "done": True})

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------- 导航信息 ----------
@app.get("/api/links", tags=["nav"])
def links():
    return {"github": config.GITHUB_URL, "gitee": config.GITEE_URL}


@app.get("/api/portfolio", tags=["nav"])
def portfolio():
    path = config.DOCS_DIR / "portfolio.md"
    if not path.exists():
        raise APIError(40401, "作品集不存在", 404)
    return {"markdown": path.read_text(encoding="utf-8")}


# ---------- 静态资源 + 首页 ----------
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(config.BASE_DIR / "static" / "index.html")
