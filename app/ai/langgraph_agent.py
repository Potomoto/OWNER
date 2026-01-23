from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.agent_model import CallModel
from app.ai.agent_stepper import decide_next_action
from app.ai.tools.registry import run_tool

"""
LangGraph的graph运行时一直在传一个state,其中最关键的state包括:
- steps: 记录了ReAct的轨迹
- action: 记录了当前模型给的下一步动作（tool/final 的 JSON dict）
- iterations: 记录了已经执行过多少次 tool

节点：
- call_model 节点：读 state（request + steps）→ 调 decide_next_action → 写 action
- run_tool 节点：读 action → 执行工具 → 把 observation append 到 steps → iterations+1
- 将之前的代码控制流变成了图控制流
"""


class AgentState(TypedDict, total=False):
    # 输入
    request: str

    # ReAct 轨迹
    steps: list[dict[str, Any]]

    # 当前“模型给的下一步动作”（tool/final 的 JSON dict）
    action: dict[str, Any]

    # 最终输出
    answer: str
    citations: list[str]

    # 计数器：已经执行过多少次 tool
    iterations: int


class LangGraphAgentResult(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    cost_ms: float
    stopped_reason: str  # final / max_steps


def build_langgraph_agent(
    *,
    db: Session,
    call_model: CallModel,
    prompt_key: str = "react_step_v1",
    max_steps: int = 5,
):
    """
    构建并编译一张最小 LangGraph：
      START -> call_model -(tool)-> run_tool -> call_model ...-> (final)-> END
    """

    async def call_model_node(state: AgentState) -> AgentState:
        iterations = int(state.get("iterations", 0))
        steps = state.get("steps", [])

        # 工程保护：硬刹车，避免无限循环
        if iterations >= max_steps:
            final_action = {
                "type": "final",
                "answer": "达到最大步骤限制仍未完成任务。请缩小问题或提高 max_steps。",
                "citations": [],
            }
            return {
                "action": final_action,
                "answer": final_action["answer"],
                "citations": [],
            }

        action = await decide_next_action(
            request=state["request"],
            steps=steps,
            prompt_key=prompt_key,
            call_model=call_model,
        )

        # model_dump 转成 dict
        action_dict = action.model_dump()

        # 如果是 final，把 answer/citations 写进 state（让 END 有可读输出）
        if action_dict.get("type") == "final":
            return {
                "action": action_dict,
                "answer": action_dict.get("answer", ""),
                "citations": action_dict.get("citations", []) or [],
            }

        # tool：只写 action，交给 run_tool 节点执行
        return {"action": action_dict}

    def route_after_call_model(state: AgentState) -> str:
        """
        条件边路由：
        - tool -> run_tool
        - final -> END
        """
        action = state.get("action") or {}
        if action.get("type") == "tool":
            return "tool"
        return "final"

    def run_tool_node(state: AgentState) -> AgentState:
        action = state.get("action") or {}
        iterations = int(state.get("iterations", 0))
        steps = state.get("steps", [])

        tool_name = action.get("tool_name")
        args = action.get("args") or {}

        obs = run_tool(db, tool_name, args)

        new_steps = list(steps)
        new_steps.append(
            {
                "step": iterations + 1,
                "action": action,
                "observation": obs,
            }
        )

        return {"steps": new_steps, "iterations": iterations + 1}

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model_node)
    graph.add_node("run_tool", run_tool_node)

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges(
        "call_model",
        route_after_call_model,
        {
            "tool": "run_tool",
            "final": END,
        },
    )
    graph.add_edge("run_tool", "call_model")

    return graph.compile()


async def run_langgraph_agent(
    *,
    db: Session,
    request: str,
    call_model: CallModel,
    prompt_key: str = "react_step_v1",
    max_steps: int = 5,
) -> LangGraphAgentResult:
    t0 = time.perf_counter()

    app = build_langgraph_agent(
        db=db,
        call_model=call_model,
        prompt_key=prompt_key,
        max_steps=max_steps,
    )

    final_state: AgentState = await app.ainvoke(
        {
            "request": request,
            "steps": [],
            "iterations": 0,
            "citations": [],
        }
    )

    answer = final_state.get("answer", "") or ""
    citations = final_state.get("citations", []) or []
    steps = final_state.get("steps", []) or []
    stopped_reason = (
        "final" if (final_state.get("action") or {}).get("type") == "final" else "unknown"
    )

    # 如果是 max_steps，我们在 call_model_node 里会强制写入那句固定答案
    if answer.startswith("达到最大步骤限制"):
        stopped_reason = "max_steps"

    return LangGraphAgentResult(
        answer=answer,
        citations=citations,
        steps=steps,
        cost_ms=(time.perf_counter() - t0) * 1000,
        stopped_reason=stopped_reason,
    )
