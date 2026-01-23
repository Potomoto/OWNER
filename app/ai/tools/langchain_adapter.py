from __future__ import annotations

from typing import Any

from langchain_core.tools.structured import StructuredTool
from sqlalchemy.orm import Session

from app.ai.tools.registry import TOOLS, run_tool

"""
LangChain的Tool有两大类：
- Tool：单输入（一般是str）
- StructuredTool：多输入（dict/多字段），更适合create/update等复杂操作
- 适配器：把你现有的工具注册表转换成LangChain的StructuredTool列表
- 其中args_schema要求是Pydantic模型
"""


def build_langchain_tools(db: Session) -> list[StructuredTool]:
    """
    把你现有 TOOLS 注册表转换成 LangChain StructuredTool 列表。
    关键点：db 通过闭包绑定（运行时注入），这样工具可以被 LangGraph/LangChain 直接调用。
    """
    tools: list[StructuredTool] = []

    for name, spec in TOOLS.items():
        # ⚠️ Python 闭包“晚绑定”坑：循环变量 name/spec 会在函数执行时变成最后一个
        # 解决：用默认参数把当前值绑定住
        def _call_tool(_name=name, **kwargs: Any) -> dict:
            return run_tool(db, _name, kwargs)

        _call_tool.__name__ = name
        _call_tool.__doc__ = spec.description

        tool = StructuredTool.from_function(
            func=_call_tool,
            name=spec.name,
            description=spec.description,
            args_schema=spec.args_model,  # ✅ 直接复用你写好的 Pydantic schema
            return_direct=False,
        )
        tools.append(tool)

    return tools
