from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app import (
    settings,
)
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import setup_logging
from app.core.middleware import log_requests
from app.db import Base, engine
from app.routers.ai import router as ai_router
from app.routers.notes import router as notes_router

# 需要让ORM见过模型（Note类），才知道应当创建哪张表，确保Note被加载


app = FastAPI(title="Notes API", version="0.1.0")

setup_logging()


@app.middleware("http")
async def ensure_json_utf8(request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset=" not in ct.lower():
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


app.include_router(ai_router)

# 中间件：记录每个请求耗时
app.middleware("http")(log_requests)

# 异常处理：统一错误格式
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

if settings.ENV == "dev":
    # 学习阶段可以保留兜底，但你要逐步习惯用 alembic upgrade head
    # 简单做法：启动时自动建表（学习阶段够用）
    Base.metadata.create_all(bind=engine)

app.include_router(notes_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
