from fastapi import FastAPI
from app.routers.notes import router as notes_router

from app.db import Base, engine
from app import models  # 这行很重要：确保 Note 模型被导入并注册到 Base
# 需要让ORM见过模型（Note类），才知道应当创建哪张表，确保Note被加载

app = FastAPI(title="Notes API", version="0.1.0")

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException

from app.core.logging import setup_logging
from app.core.middleware import log_requests
from app.core.errors import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)

setup_logging()

app = FastAPI()

# 中间件：记录每个请求耗时
app.middleware("http")(log_requests)

# 异常处理：统一错误格式
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# 简单做法：启动时自动建表（学习阶段够用）
Base.metadata.create_all(bind=engine)

app.include_router(notes_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
