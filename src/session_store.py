"""会话存储：MySQL 多会话持久化（sessions + messages 两张表，SQLAlchemy ORM）。

对比旧版 sqlite3 直写：这里用 ORM 模型 + 连接池 + 事务，字段类型与 scripts/schema.sql 一一对应。
"""
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Index, Integer, String, Text, create_engine, func, select, text
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

Base = declarative_base()


class Session(Base):
    """会话表（对应 schema.sql 的 sessions）。"""
    __tablename__ = "sessions"

    id = Column(CHAR(32), primary_key=True)             # uuid hex 固定 32 位 → 定长 CHAR
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Message(Base):
    """消息表（对应 schema.sql 的 messages）。"""
    __tablename__ = "messages"
    __table_args__ = (Index("idx_session_id", "session_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(CHAR(32), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(16), nullable=False)           # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)               # JSON 串，供「源文本」按钮
    created_at = Column(DateTime, nullable=False)


class User(Base):
    """用户表（对应 schema.sql 的 users）。"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)   # 唯一：防重名 + 加速登录查询
    password_hash = Column(String(255), nullable=False)          # 只存哈希，绝不存明文
    created_at = Column(DateTime, nullable=False)


# SQLite（测试环境）要关掉「同线程检查」：FastAPI 的同步接口跑在线程池里，
# 同一条连接会被不同线程用到。MySQL 没这个限制，所以只在 sqlite 时才加这个参数。
_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

# 引擎（内置连接池：pool_pre_ping 踢掉失效连接，pool_recycle 防 MySQL 8h 断连）
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _now() -> datetime:
    """当前 UTC 时间（naive）。MySQL DATETIME 不带时区，所以存 naive UTC。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str:
    """datetime → ISO 字符串。MySQL 读回是 datetime 对象，转回字符串以保持对外接口不变。"""
    return dt.isoformat() if dt else ""


@contextmanager
def _session():
    """SQLAlchemy 会话上下文：成功提交、异常回滚、用完关闭（连接归还池子）。"""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """建表（幂等）。表已由 schema.sql 建好，这里兜底 + 顺带验证连接可用。"""
    Base.metadata.create_all(engine)


def ping() -> bool:
    """探测数据库连通性：能跑通一条最简 SQL 就算通。

    给 /healthz 用。不抛异常、只返回布尔——健康检查不该因为
    「探查本身出错」而整个炸掉，它需要的是「能/不能」这个结论。
    """
    try:
        with _session() as s:
            s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def create_session(user_id: int, title: str = "") -> dict:
    """新建会话（归属某用户），返回 {id, title, created_at, updated_at}。"""
    sid = uuid.uuid4().hex
    now = _now()
    with _session() as s:
        s.add(Session(id=sid, user_id=user_id, title=title, created_at=now, updated_at=now))
    return {"id": sid, "title": title, "created_at": _iso(now), "updated_at": _iso(now)}


def list_sessions(user_id: int, offset: int = 0, limit: int = 20) -> dict:
    """某用户的会话列表（分页），按最近更新时间倒序。返回 {items, total, offset, limit}。"""
    with _session() as s:
        total = s.scalar(select(func.count()).select_from(Session).where(Session.user_id == user_id))
        rows = s.scalars(
            select(Session).where(Session.user_id == user_id)
            .order_by(Session.updated_at.desc()).offset(offset).limit(limit)
        ).all()
        items = [
            {"id": r.id, "title": r.title, "created_at": _iso(r.created_at), "updated_at": _iso(r.updated_at)}
            for r in rows
        ]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def get_session(session_id: str, user_id: int) -> dict | None:
    """取某用户的单个会话；不属于该用户或不存在返回 None。"""
    with _session() as s:
        r = s.scalar(select(Session).where(Session.id == session_id, Session.user_id == user_id))
        if r is None:
            return None
        return {"id": r.id, "title": r.title, "created_at": _iso(r.created_at), "updated_at": _iso(r.updated_at)}


def delete_session(session_id: str, user_id: int) -> bool:
    """删除某用户的会话；消息由外键 ON DELETE CASCADE 自动删除。返回是否真删到。"""
    with _session() as s:
        r = s.scalar(select(Session).where(Session.id == session_id, Session.user_id == user_id))
        if r is None:
            return False
        s.delete(r)
        return True


def add_message(session_id: str, role: str, content: str, sources: list[dict] | None = None) -> None:
    """追加一条消息；顺带维护会话标题与更新时间（同一个事务里完成）。"""
    now = _now()
    sources_json = json.dumps(sources, ensure_ascii=False) if sources else None
    with _session() as s:
        s.add(Message(session_id=session_id, role=role, content=content, sources=sources_json, created_at=now))
        sess = s.get(Session, session_id)
        if sess is not None:
            # 会话标题为空时，用第一句用户提问前 20 字当标题
            if role == "user" and not sess.title:
                sess.title = content.strip().replace("\n", " ")[:20]
            sess.updated_at = now                     # 会话列表按它排序


def get_messages(session_id: str) -> list[dict]:
    """取某会话全部消息（按时间正序），sources 反序列化为 list。"""
    with _session() as s:
        rows = s.scalars(
            select(Message).where(Message.session_id == session_id).order_by(Message.id.asc())
        ).all()
        result = []
        for r in rows:
            src = None
            if r.sources:
                try:
                    src = json.loads(r.sources)
                except json.JSONDecodeError:
                    src = None
            result.append({"role": r.role, "content": r.content, "sources": src, "created_at": _iso(r.created_at)})
        return result
