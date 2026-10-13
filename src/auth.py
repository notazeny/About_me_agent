"""用户鉴权：注册 / 登录 + 密码哈希（bcrypt）。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import config
from .errors import APIError
from .session_store import User, _now, _session


def hash_password(password: str) -> str:
    """bcrypt 哈希：自带盐 + 慢哈希，防暴力破解和彩虹表。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码（checkpw 内部做常数时间比较，防时序攻击）。"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def register(username: str, password: str) -> dict:
    """注册新用户。用户名重复：先查给友好报错，唯一索引兜底（并发时靠它拦截）。"""
    try:
        with _session() as s:
            exists = s.scalar(select(User).where(User.username == username))
            if exists:
                raise ValueError("用户名已存在")
            user = User(username=username, password_hash=hash_password(password), created_at=_now())
            s.add(user)
            s.flush()                      # 立即发 INSERT（拿到自增 id + 触发唯一约束检查）
            result = {"id": user.id, "username": user.username}
    except IntegrityError:
        # 并发注册同名：先查和插入之间有空隙，唯一索引是真正的兜底
        raise ValueError("用户名已存在")
    return result


def create_token(user_id: int, username: str) -> str:
    """签发 JWT。payload 带 sub（用户 id）+ exp（过期时间）。无状态，服务端不存。"""
    exp = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "username": username, "exp": exp}
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """校验 JWT 并返回 payload；无效 / 过期会抛 jwt 异常。"""
    return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])


def login(username: str, password: str) -> dict:
    """登录：校验密码后签发 token。用户名或密码错都返回同样的错（不泄露是哪个错了）。"""
    with _session() as s:
        user = s.scalar(select(User).where(User.username == username))
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("用户名或密码错误")
        token = create_token(user.id, user.username)
        return {"id": user.id, "username": user.username, "token": token}


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI 依赖：从 Authorization: Bearer <token> 里解析出当前用户。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise APIError(40101, "未登录", 401)
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise APIError(40102, "登录已过期，请重新登录", 401)
    except jwt.InvalidTokenError:
        raise APIError(40102, "token 无效", 401)
    return {"id": int(payload["sub"]), "username": payload.get("username", "")}
