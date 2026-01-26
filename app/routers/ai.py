# app/routers/ai.py
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.agent_model import CallModel, get_agent_call_model
from app.ai.ai_service import rewrite, summarize
from app.ai.langgraph_agent import get_langgraph_state, run_langgraph_agent
from app.ai.output_schemas import RewriteOut, SummaryOut
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
    thread_id: str | None = None
    max_steps: int = Field(5, ge=1, le=10)
    prompt_key: str = "react_step_v1"
    debug: bool = True


class AgentRunOut(BaseModel):
    thread_id: str
    answer: str
    citations: list[str] = []
    steps: list[dict] = []
    stopped_reason: str


class AgentStateOut(BaseModel):
    thread_id: str
    steps_count: int
    last_action: dict[str, Any] | None = None
    last_observation_ok: bool | None = None
    next: list[str] = []


@router.post("/agent/run")
async def agent_run(
    body: AgentRunIn,
    db: Session = Depends(get_db),
    call_model: CallModel = Depends(get_agent_call_model),
):
    thread_id, result = await run_langgraph_agent(
        db=db,
        request=body.request,
        call_model=call_model,
        max_steps=body.max_steps,
        prompt_key=body.prompt_key,
        thread_id=body.thread_id,
        checkpoint_db_path="agent_checkpoints.sqlite3",
    )

    out = {
        "thread_id": thread_id,
        "answer": result.answer,
        "citations": result.citations,
        "steps": result.steps if body.debug else [],
        "stopped_reason": result.stopped_reason,
    }
    return out


@router.get("/agent/state/{thread_id}", response_model=AgentStateOut)
async def agent_state(
    thread_id: str,
    db: Session = Depends(get_db),
    call_model: CallModel = Depends(get_agent_call_model),
):
    return await get_langgraph_state(
        db=db,
        call_model=call_model,
        thread_id=thread_id,
        checkpoint_db_path="agent_checkpoints.sqlite3",
    )
