"""统一错误码 + 全局异常处理。

错误码约定（前端据此分支，而不是解析中文 message）：
  40001 参数错误 / 输入不合法
  40002 用户名已存在
  40101 未登录（缺 Authorization）
  40102 token 无效或过期
  40103 用户名或密码错误
  40401 资源不存在
  42901 请求太频繁
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse


class APIError(Exception):
    """业务异常：带稳定错误码。"""
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    """把 APIError 统一转成 {code, message, data} 响应。"""
    @app.exception_handler(APIError)
    async def _handle_api_error(request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "data": None},
        )
