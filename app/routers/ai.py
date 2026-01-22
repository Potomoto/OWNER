# app/routers/ai.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.agent_model import CallModel, get_agent_call_model
from app.ai.ai_service import rewrite, summarize
from app.ai.output_schemas import RewriteOut, SummaryOut
from app.ai.react_agent import AgentRunResult, run_react_agent
from app.db import get_db
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


class AgentRunIn(BaseModel):
    request: str = Field(..., min_length=1)
    max_steps: int = Field(5, ge=1, le=10)
    prompt_key: str = "react_step_v1"
    debug: bool = True


@router.post("/agent/run", response_model=AgentRunResult)
async def agent_run_api(
    body: AgentRunIn,
    db: Session = Depends(get_db),
    call_model: CallModel = Depends(get_agent_call_model),  # ✅ 真实模型调用注入
):
    result = await run_react_agent(
        db=db,
        request=body.request,
        call_model=call_model,
        max_steps=body.max_steps,
        prompt_key=body.prompt_key,
    )

    # debug=false 时不返回 steps（生产里通常会关掉）
    if not body.debug:
        result.steps = []

    return result
