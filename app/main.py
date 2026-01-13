from fastapi import FastAPI
from app.routers.notes import router as notes_router

app = FastAPI(title="Notes API", version="0.1.0")

# 版本管理方式，v1为版本号，将这个路由组统一加前缀/v1，未来可以有/v2
app.include_router(notes_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}