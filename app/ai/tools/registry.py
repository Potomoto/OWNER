import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Type

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from . import notes_tools
from .schemas import CreateNoteArgs, DeleteNoteArgs, GetNoteArgs, SearchNotesArgs, UpdateNoteArgs

logger = logging.getLogger("ai.tools")

"""
使用ToolSpec 来定义每个工具的元信息，该注册表可以实现：
- 自动生成工具列表给prompt
- 快速增减工具项
- 做权限和灰度，某些工具会只开放给特定用户/场景，注册表支持过滤
"""


@dataclass(frozen=True)
class ToolSpec:
    """
    ToolSpec = 一个工具的“元信息”：
    - name：工具名（模型会输出这个字符串）
    - description：给模型看的说明（越短越清晰越好）
    - args_model：参数 schema（Pydantic）
    - func：真正执行的 Python 函数
    """

    name: str
    description: str
    args_model: Type[BaseModel]
    func: Callable[[Session, BaseModel], Any]


TOOLS: dict[str, ToolSpec] = {
    "search_notes": ToolSpec(
        name="search_notes",
        description="Search notes by keyword in title/content. Return id/title/snippet list.",
        args_model=SearchNotesArgs,
        func=notes_tools.search_notes,
    ),
    "get_note": ToolSpec(
        name="get_note",
        description="Get a note by id.",
        args_model=GetNoteArgs,
        func=notes_tools.get_note,
    ),
    "create_note": ToolSpec(
        name="create_note",
        description="Create a note with title/content.",
        args_model=CreateNoteArgs,
        func=notes_tools.create_note,
    ),
    "update_note": ToolSpec(
        name="update_note",
        description="Partially update a note by id (title/content optional).",
        args_model=UpdateNoteArgs,
        func=notes_tools.update_note,
    ),
    "delete_note": ToolSpec(
        name="delete_note",
        description="Delete a note by id.",
        args_model=DeleteNoteArgs,
        func=notes_tools.delete_note,
    ),
}


def format_tools_for_prompt() -> str:
    """
    给 prompt 用的工具清单（短 + 稳定）。
    未来 Session18 你会把它注入到 react_step prompt 里。
    """
    lines: list[str] = []
    for name, spec in TOOLS.items():
        fields = list(spec.args_model.model_fields.keys())
        lines.append(f"- {name}: {spec.description} Args: {fields}")
    return "\n".join(lines)


def run_tool(db: Session, tool_name: str, args: dict) -> dict:
    """
    统一工具执行入口（非常关键）：

    1) 校验 tool 是否存在
    2) 用 Pydantic 校验 args
    3) 执行工具
    4) 捕获异常，返回稳定结构（ok/error）
    """
    if tool_name not in TOOLS:
        return {
            "ok": False,
            "tool_name": tool_name,
            "error": {
                "code": "unknown_tool",
                "message": f"Unknown tool: {tool_name}",
                "details": None,
            },
        }

    spec = TOOLS[tool_name]
    t0 = time.perf_counter()

    try:
        parsed_args = spec.args_model.model_validate(args)
    except ValidationError as e:
        return {
            "ok": False,
            "tool_name": tool_name,
            "error": {
                "code": "invalid_args",
                "message": "Tool args validation failed",
                "details": e.errors(),
            },
        }

    try:
        data = spec.func(db, parsed_args)
        cost_ms = (time.perf_counter() - t0) * 1000
        logger.info("tool_ok name=%s cost_ms=%.1f", tool_name, cost_ms)
        return {"ok": True, "tool_name": tool_name, "cost_ms": cost_ms, "data": data}

    except HTTPException as e:
        # 兼容 NotesService.get/delete 抛的 HTTPException
        cost_ms = (time.perf_counter() - t0) * 1000
        code = "not_found" if e.status_code == 404 else "http_error"
        logger.warning(
            "tool_http_error name=%s status=%s cost_ms=%.1f", tool_name, e.status_code, cost_ms
        )
        return {
            "ok": False,
            "tool_name": tool_name,
            "cost_ms": cost_ms,
            "error": {
                "code": code,
                "message": str(e.detail),
                "details": {"status_code": e.status_code},
            },
        }

    except Exception as e:
        # 兜底：防止工具炸掉导致 agent/接口 500
        cost_ms = (time.perf_counter() - t0) * 1000
        logger.exception("tool_exception name=%s cost_ms=%.1f", tool_name, cost_ms)
        return {
            "ok": False,
            "tool_name": tool_name,
            "cost_ms": cost_ms,
            "error": {"code": "tool_exception", "message": str(e)[:200], "details": None},
        }
