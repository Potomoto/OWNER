# app/core/errors.py
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("error")

# 对error返回格式进行规范
def error_response(code: str, message: str, status_code: int, details=None) -> JSONResponse:
    """
    全项目统一错误返回结构：
    {
      "error": {
        "code": "invalid_api_key",
        "message": "Invalid API key",
        "details": ...
      }
    }
    """
    payload = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=payload)

# 规定错误代码对应的名称
async def http_exception_handler(request: Request, exc: HTTPException):
    # 你可以根据 status_code 自定义 code
    code = "http_error"
    if exc.status_code == 401:
        code = "unauthorized"
    elif exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 500:
        code = "server_misconfigured"

    return error_response(code=code, message=str(exc.detail), status_code=exc.status_code)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 422：请求参数不符合 pydantic 校验（FastAPI 的常见错误）
    return error_response(
        code="validation_error",
        message="Request validation failed",
        status_code=422,
        details=exc.errors(),
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    捕获未处理异常：
    - 返回统一 500
    - 日志记录堆栈（logger.exception 会自动打印 traceback）
    """
    logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
    return error_response(
        code="internal_error",
        message="Internal server error",
        status_code=500,
    )
