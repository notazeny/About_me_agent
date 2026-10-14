"""可观测：请求 ID + 结构化访问日志。

## 为什么需要这个

默认的 uvicorn 访问日志长这样：

    INFO: 124.240.42.104:0 - "GET /sessions HTTP/1.1" 401

**没有请求 ID、没有耗时、没有业务上下文。** 一旦线上出问题——
比如某个 HR 说「我提问的时候报错了」——你根本无从查起：
那条请求混在成千上万行里，没有任何线索能把它单独拎出来。

请求 ID 就是那根线：给每次请求发一张身份证，
它在访问日志里、在业务日志里、在返回给前端的响应头里都一致。
排查时 grep 这一个 ID，整条请求的来龙去脉一目了然。

## 一个反直觉的点

对 SSE（流式聊天）这种请求，中间件测到的**不是总耗时，而是「首字节耗时」**——
因为 `call_next` 在响应头就绪时就返回了，正文是之后才慢慢流的。

听起来像缺陷，**其实正好**：用户感知最强的恰恰是「等多久才蹦出第一个字」
（TTFT），而不是后台总共花了多久。所以这个数字对 SSE 反而更有意义。
"""

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

# 单独一个 logger，名字里带模块名，方便在日志系统里按来源过滤
logger = logging.getLogger("aboutme.access")
logger.setLevel(logging.INFO)

# 自己挂一个 handler 输出到 stderr（systemd 会收进 journald）。
# 不去动 root logger 的配置，避免和 uvicorn 自己的日志配置打架。
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))   # 消息本身就是 JSON，不再加前缀
    logger.addHandler(_handler)
    logger.propagate = False        # 不往 root 传，避免重复输出


def _client_ip(request) -> str:
    """取真实客户端 IP。

    套了 Nginx 之后 `request.client.host` 是 127.0.0.1（Nginx 自己），
    真实 IP 在 Nginx 透传的 X-Real-IP 里。
    """
    return (
        request.headers.get("X-Real-IP")
        or (request.client.host if request.client else "-")
    )


class AccessLogMiddleware(BaseHTTPMiddleware):
    """给每个请求分配 ID，并记一条结构化（JSON）访问日志。"""

    async def dispatch(self, request, call_next):
        # 优先沿用上游传进来的 ID：Nginx / 前端如果带了 X-Request-ID，
        # 就用它 —— 这样一条请求跨多个服务时 ID 是连贯的（链路追踪的雏形）。
        # 没有就自己生成一个。
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

        # perf_counter 是单调时钟，不受系统时间被调整的影响，适合测耗时
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # 出异常也要留痕 —— 否则「500 了但日志里什么都没有」最难查。
            # logger.exception 会带上完整堆栈。
            logger.exception(json.dumps({
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
                "client": _client_ip(request),
            }, ensure_ascii=False))
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        # 把 ID 回写给前端：用户报错时前端可以把 ID 显示出来，
        # 用户截图给你，你直接 grep 这个 ID —— 排查从「大海捞针」变「精确制导」。
        response.headers["X-Request-ID"] = request_id

        logger.info(json.dumps({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            # 对 SSE 而言这是「首字节耗时」而非总耗时（见模块开头说明）
            "elapsed_ms": elapsed_ms,
            "client": _client_ip(request),
        }, ensure_ascii=False))

        return response
