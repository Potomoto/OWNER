# app/core/middleware.py
import logging
import time
from fastapi import Request

"""
    - 中间件（middleware）是一层统一拦截器
    - 路由执行前后都能工作：记录耗时、加header、限流、审计等
"""
logger = logging.getLogger("request")


async def log_requests(request: Request, call_next):
    """
    FastAPI 中间件：
    - 每个请求进来都会经过这里
    - call_next(request) 会继续执行路由逻辑并拿到 response
    """
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000

        # 注意：response 可能在异常时为 None
        status_code = getattr(response, "status_code", 500)

        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )
