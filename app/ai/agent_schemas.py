from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """
    模型决定：下一步要调用工具
    """

    type: Literal["tool"] = "tool"
    tool_name: str = Field(..., min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)


class FinalAnswer(BaseModel):
    """
    模型决定：直接输出最终回答（不再调用工具）
    """

    type: Literal["final"] = "final"
    answer: str = Field(..., min_length=1, description="Final answer in Simplified Chinese")
    citations: list[str] = Field(
        default_factory=list, description="Optional references like note:12"
    )


AgentAction = ToolCall | FinalAnswer
