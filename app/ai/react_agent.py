from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.agent_model import CallModel
from app.ai.agent_schemas import FinalAnswer, ToolCall
from app.ai.agent_stepper import decide_next_action
from app.ai.tools.registry import run_tool


class AgentRunResult(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    cost_ms: float
    stopped_reason: str


async def run_react_agent(
    *,
    db: Session,
    request: str,
    call_model: CallModel,
    max_steps: int = 5,
    prompt_key: str = "react_step_v1",
) -> AgentRunResult:
    """
    ReAct 核心循环：
    1) 模型决定下一步（tool / final）
    2) 如果 tool：执行工具，把 observation 记录到 steps
    3) 如果 final：返回最终答案
    4) 有 max_steps 防止跑飞
    """
    steps: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for i in range(max_steps):
        action = await decide_next_action(
            request=request,
            steps=steps,
            prompt_key=prompt_key,
            call_model=call_model,  # ✅ 真实模型/假模型都从这里注入
        )

        if isinstance(action, FinalAnswer):
            return AgentRunResult(
                answer=action.answer,
                citations=action.citations,
                steps=steps,
                cost_ms=(time.perf_counter() - t0) * 1000,
                stopped_reason="final",
            )

        # tool action
        assert isinstance(action, ToolCall)

        obs = run_tool(db, action.tool_name, action.args)

        steps.append(
            {
                "step": i + 1,
                "action": action.model_dump(),
                "observation": obs,
            }
        )

        # 如果工具执行失败（ok=False），让循环继续，让模型调整策略（这正是 agent 的意义）
        # 但你也可以做一个保护：连续失败 N 次就停止（先不加，后面再迭代）

    return AgentRunResult(
        answer="达到最大步骤限制仍未完成任务。请缩小问题或提高 max_steps。",
        citations=[],
        steps=steps,
        cost_ms=(time.perf_counter() - t0) * 1000,
        stopped_reason="max_steps",
    )
