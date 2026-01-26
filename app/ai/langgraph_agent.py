# app/ai/langgraph_agent.py
from __future__ import annotations

import re
import time
import uuid
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.agent_model import CallModel
from app.ai.agent_stepper import decide_next_action
from app.ai.checkpointers import make_async_sqlite_saver
from app.ai.tools.registry import run_tool

"""
LangGraph 的 graph 运行时一直在传一个 state, 其中最关键的 state 包括:
- steps: 记录 ReAct 轨迹（本版本：直接裁剪 = 覆盖式写回）
- action: 当前模型给的下一步动作（tool/final 的 JSON dict）
- iterations: 已执行多少次 tool（硬刹车用）
"""

# ----------------------------
# State + Result Schemas
# ----------------------------


class AgentState(TypedDict, total=False):
    request: str

    # ✅ 直接裁剪版：steps 是普通字段（不再使用 reducer/operator.add）
    steps: list[dict[str, Any]]

    # 当前动作
    action: dict[str, Any]

    # 最终输出
    answer: str
    citations: list[str]

    # 计数器：已经执行过多少次 tool
    iterations: int

    # ✅ 结构化停止原因
    stopped_reason: str  # final / max_steps / error


class LangGraphAgentResult(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    cost_ms: float
    stopped_reason: str  # final / max_steps / error


# ----------------------------
# Agent builder
# ----------------------------


def _trim_steps(steps: list[dict], keep_last: int) -> list[dict]:
    if keep_last <= 0:
        return []
    if len(steps) <= keep_last:
        return steps
    return steps[-keep_last:]


def build_langgraph_agent(
    *,
    db: Session,
    call_model: CallModel,
    prompt_key: str = "react_step_v1",
    max_steps: int = 5,
    checkpointer=None,
    memory_max_steps: int = 20,
):
    """
    构建并编译一张最小 LangGraph：
      START -> call_model -(tool)-> run_tool -> call_model ...-> (final)-> END

    ✅ 本版本：steps 直接裁剪（覆盖式写回 state），因此不再使用 reducer(add)。
    """

    async def call_model_node(state: AgentState) -> AgentState:
        iterations = int(state.get("iterations", 0))
        steps = state.get("steps", []) or []
        req = state.get("request", "") or ""

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
                "stopped_reason": "max_steps",
            }

        # ✅ 你也可以在这里“只给模型看裁剪后的 steps”
        # 但注意：这不会改变 state 本身（state 本身的裁剪在 run_tool_node 做）
        if memory_max_steps is not None:
            steps_for_model = _trim_steps(steps, memory_max_steps)
        else:
            steps_for_model = steps

        action = await decide_next_action(
            request=req,
            steps=steps_for_model,
            prompt_key=prompt_key,
            call_model=call_model,
        )

        action_dict = action.model_dump()

        # ✅ 工程硬约束：创建笔记类请求，第一步必须 create_note
        if iterations == 0:
            want_create = (
                ("创建" in req) or ("新增" in req) or ("记录" in req) or ("create" in req.lower())
            )
            if want_create:
                is_create_first = (
                    action_dict.get("type") == "tool"
                    and action_dict.get("tool_name") == "create_note"
                )
                if not is_create_first:
                    m_title = re.search(r"标题为([^\s，。]+)", req)
                    m_content = re.search(r"内容为[:：]\s*(.+)$", req)
                    title = m_title.group(1) if m_title else "未命名"
                    content = m_content.group(1) if m_content else req
                    action_dict = {
                        "type": "tool",
                        "tool_name": "create_note",
                        "args": {"title": title, "content": content},
                    }

        if action_dict.get("type") == "final":
            return {
                "action": action_dict,
                "answer": action_dict.get("answer", "") or "",
                "citations": action_dict.get("citations", []) or [],
                "stopped_reason": "final",
            }

        return {"action": action_dict}

    def route_after_call_model(state: AgentState) -> str:
        action = state.get("action") or {}
        if action.get("type") == "tool":
            return "tool"
        return "final"

    def run_tool_node(state: AgentState) -> AgentState:
        """
        ✅ 直接裁剪的核心在这里：
        - 读出历史 steps
        - append 新 step
        - 立刻 trim
        - 返回完整 steps（覆盖写回 state）
        """
        action = state.get("action") or {}
        iterations = int(state.get("iterations", 0))
        steps = state.get("steps", []) or []

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

        # ✅ 直接裁剪：覆盖式写回 state（SQLite 里也只会保存裁剪后的 steps）
        if memory_max_steps is not None:
            new_steps = _trim_steps(new_steps, memory_max_steps)

        return {"steps": new_steps, "iterations": iterations + 1}

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model_node)
    graph.add_node("run_tool", run_tool_node)

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges(
        "call_model",
        route_after_call_model,
        {"tool": "run_tool", "final": END},
    )
    graph.add_edge("run_tool", "call_model")

    return graph.compile(checkpointer=checkpointer)


# ----------------------------
# Public APIs
# ----------------------------


async def run_langgraph_agent(
    *,
    db: Session,
    request: str,
    call_model: CallModel,
    prompt_key: str = "react_step_v1",
    max_steps: int = 5,
    thread_id: str | None = None,
    checkpoint_db_path: str = "agent_checkpoints.sqlite3",
) -> tuple[str, LangGraphAgentResult]:
    if not thread_id:
        thread_id = str(uuid.uuid4())

    t0 = time.perf_counter()

    handle = await make_async_sqlite_saver(checkpoint_db_path)
    try:
        app = build_langgraph_agent(
            db=db,
            call_model=call_model,
            prompt_key=prompt_key,
            max_steps=max_steps,
            checkpointer=handle.saver,
        )

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        final_state = await app.ainvoke({"request": request}, config)

        stopped_reason = final_state.get("stopped_reason", "unknown") or "unknown"

        result = LangGraphAgentResult(
            answer=final_state.get("answer", "") or "",
            citations=final_state.get("citations", []) or [],
            steps=final_state.get("steps", []) or [],
            cost_ms=(time.perf_counter() - t0) * 1000,
            stopped_reason=stopped_reason,
        )
        return thread_id, result
    finally:
        await handle.conn.close()


async def get_langgraph_state(
    *,
    db: Session,
    call_model: CallModel,
    thread_id: str,
    prompt_key: str = "react_step_v1",
    max_steps: int = 5,
    checkpoint_db_path: str = "agent_checkpoints.sqlite3",
) -> dict:
    handle = await make_async_sqlite_saver(checkpoint_db_path)
    try:
        app = build_langgraph_agent(
            db=db,
            call_model=call_model,
            prompt_key=prompt_key,
            max_steps=max_steps,
            checkpointer=handle.saver,
        )

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await app.aget_state(config)

        values = snapshot.values or {}
        steps = values.get("steps", []) or []
        last = steps[-1] if steps else None

        return {
            "thread_id": thread_id,
            "steps_count": len(steps),
            "last_action": (last or {}).get("action"),
            "last_observation_ok": ((last or {}).get("observation") or {}).get("ok"),
            "next": list(snapshot.next) if getattr(snapshot, "next", None) is not None else [],
        }
    finally:
        await handle.conn.close()
