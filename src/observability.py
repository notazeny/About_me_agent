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

## 流式响应为什么要特殊处理（实测踩过的坑）

第一版直接在 `call_next` 之后记 `elapsed_ms`，结果 chat 请求记出来 **47ms**，
而实际耗时约 **13 秒**。

原因：`call_next` 对 `StreamingResponse` 是在「**响应对象构造完成**」时就返回的，
此时检索、rerank、调 LLM 这些活儿**一个字都还没开始**（它们写在后面的生成器里，
是被逐块消费时才执行的）。所以那个 47ms 测的是「准备响应」的耗时，毫无意义。

**教训：凭直觉写的时间测量，一定要实测校准。** 这句话本身就是可观测的意义。

现在的做法：对流式响应**包装正文迭代器**，等真正流完再记日志，
并额外记下 `ttfb_ms`（首字节耗时）——对聊天这类接口，
用户感知最强的恰恰是「等多久才蹦出第一个字」。
"""

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

# ---- 关掉 uvicorn 自带的访问日志 ----
# 我们自己的结构化日志已经完全覆盖它。留着只会让每条请求打两遍，
# 日志量翻倍、噪音变大（实测被 sazeny 一眼看出来了）。
logging.getLogger("uvicorn.access").disabled = True

# 单独一个 logger，名字带模块名，方便日志系统里按来源过滤
logger = logging.getLogger("aboutme.access")
logger.setLevel(logging.INFO)

# 自己挂 handler 输出到 stderr（systemd 收进 journald）。
# 不去动 root logger 的配置，避免和 uvicorn 的日志配置打架。
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))   # 消息本身就是 JSON
    logger.addHandler(_handler)
    logger.propagate = False        # 不往 root 传，避免重复输出


def _client_ip(request) -> str:
    """取真实客户端 IP。

    套了 Nginx 之后 `request.client.host` 恒为 127.0.0.1（Nginx 自己），
    真实 IP 在 Nginx 透传的 X-Real-IP 里。
    """
    return (
        request.headers.get("X-Real-IP")
        or (request.client.host if request.client else "-")
    )


class AccessLogMiddleware(BaseHTTPMiddleware):
    """给每个请求分配 ID，并记一条结构化（JSON）访问日志。"""

    async def dispatch(self, request, call_next):
        # 优先沿用上游传进来的 ID：Nginx / 前端带了 X-Request-ID 就用它——
        # 这样一条请求跨多个服务时 ID 连贯（链路追踪的雏形）。没有就自己生成。
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

        # 挂到 request.state，让下游（比如 chat 端点）也能拿到同一个 ID
        request.state.request_id = request_id

        # perf_counter 是单调时钟，不受系统时间被调整的影响，适合测耗时
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # 出异常也要留痕——否则「500 了但日志里什么都没有」最难查。
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

        # 把 ID 回写给前端：用户报错时前端可以显示出来，
        # 用户截图给你，你直接 grep 这个 ID——从「大海捞针」变「精确制导」。
        response.headers["X-Request-ID"] = request_id

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("text/event-stream"):
            # 流式响应：正文还没开始生成，包装迭代器，等流完再记（见模块开头说明）
            response.body_iterator = self._logged_stream(
                response.body_iterator, request, request_id, response.status_code, start
            )
        else:
            # 普通响应：正文已在响应对象里，直接记
            logger.info(json.dumps(
                self._fields(request, request_id, response.status_code, start),
                ensure_ascii=False,
            ))

        return response

    @staticmethod
    def _fields(request, request_id, status, start) -> dict:
        return {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
            "client": _client_ip(request),
        }

    async def _logged_stream(self, body_iterator, request, request_id, status, start):
        """逐块转发正文，同时记录首字节耗时与总耗时。"""
        ttfb_ms = None
        try:
            async for chunk in body_iterator:
                if ttfb_ms is None and chunk:
                    ttfb_ms = round((time.perf_counter() - start) * 1000, 1)
                yield chunk
        finally:
            # finally 保证「客户端中途断开」也会记上（此时会抛 GeneratorExit）
            fields = self._fields(request, request_id, status, start)
            fields["stream"] = True
            fields["ttfb_ms"] = ttfb_ms        # 首字节耗时：用户感知最强的指标
            logger.info(json.dumps(fields, ensure_ascii=False))
