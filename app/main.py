from fastapi import FastAPI
from app.routers.notes import router as notes_router

app = FastAPI(title="Notes API", version="0.1.0")

app.include_router(notes_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}