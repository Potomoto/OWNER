# app/routers/ai.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ai.ai_service import rewrite, summarize
from app.ai.output_schemas import RewriteOut, SummaryOut
from app.security import verify_api_key

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(verify_api_key)],  # 继续沿用你现有的 X-API-Key 保护
)


class SummarizeIn(BaseModel):
    content: str = Field(..., min_length=1)
    prompt_key: str = "summarize_v1"


class RewriteIn(BaseModel):
    content: str = Field(..., min_length=1)
    style: str = Field(..., min_length=1)
    prompt_key: str = "rewrite_v1"


@router.post("/summarize", response_model=SummaryOut)
async def summarize_api(body: SummarizeIn):
    return await summarize(content=body.content, prompt_key=body.prompt_key)


@router.post("/rewrite", response_model=RewriteOut)
async def rewrite_api(body: RewriteIn):
    return await rewrite(content=body.content, style=body.style, prompt_key=body.prompt_key)
