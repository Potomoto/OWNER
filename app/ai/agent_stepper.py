from __future__ import annotations

import json
from typing import Awaitable, Callable

from pydantic import ValidationError

from app.ai.agent_schemas import AgentAction, FinalAnswer, ToolCall
from app.ai.prompt_render import render_prompt
from app.ai.tools.registry import TOOLS, format_tools_for_prompt

"""
    1.生成 tools_text（从工具注册表生成）
    2.把 request + tools + history 塞进 prompt 模板
    3.调模型得到 dict（测试时可注入 fake_model）
    4.用 schema 校验，并额外校验 tool_name/args
"""
# call_model 的签名：输入 prompt，输出“已解析的 dict”
CallModel = Callable[[str], Awaitable[dict]]


def _steps_to_history_json(steps: list[dict]) -> str:
    """
    给模型看的 history：结构化 JSON（尽量短）
    """
    if not steps:
        return "[]"
    return json.dumps(steps, ensure_ascii=False, indent=2)


def _validate_action(data: dict) -> AgentAction:
    """
    先用 Pydantic 校验 ToolCall/FinalAnswer，
    再做“工程约束校验”（tool 是否存在、args 是否符合 schema）。
    """
    t = data.get("type")
    if t == "tool":
        action = ToolCall.model_validate(data)
        # 工程约束 1：tool_name 必须存在
        if action.tool_name not in TOOLS:
            raise ValueError(f"Unknown tool chosen by model: {action.tool_name}")

        # 工程约束 2：args 必须符合该工具的 args_model
        spec = TOOLS[action.tool_name]
        spec.args_model.model_validate(action.args)

        return action

    if t == "final":
        return FinalAnswer.model_validate(data)

    raise ValueError(f"Invalid action type: {t}")


async def decide_next_action(
    *,
    request: str,
    steps: list[dict],
    prompt_key: str = "react_step_v1",
    call_model: CallModel | None = None,
) -> AgentAction:
    """
    让模型输出下一步动作（tool 或 final）。

    call_model:
    - 测试时注入 fake_model，避免依赖真实模型/网络
    - 线上默认用你的真实模型 client（你在下面的 _default_call_model 里接）
    """
    tools_text = format_tools_for_prompt()
    history_json = _steps_to_history_json(steps)

    prompt = render_prompt(
        prompt_key,
        request=request,
        tools=tools_text,
        history_json=history_json,
    )

    if call_model is None:
        call_model = _default_call_model()

    # 第一次尝试
    data = await call_model(prompt)
    try:
        return _validate_action(data)
    except (ValidationError, ValueError) as e:
        # ✅ 推荐：自动重试一次（让模型修复 JSON）
        repair_prompt = _build_repair_prompt(prompt, data, str(e))
        data2 = await call_model(repair_prompt)
        return _validate_action(data2)


def _build_repair_prompt(original_prompt: str, bad_output: dict, error_msg: str) -> str:
    """
    JSON 修复策略：把错误原因+坏输出告诉模型，让它只输出正确 JSON
    """
    return (
        "Your previous output is invalid.\n"
        f"Error: {error_msg}\n\n"
        "You MUST output valid JSON ONLY, following the required format.\n"
        "Do NOT output any extra text.\n\n"
        "Original task prompt:\n"
        f"{original_prompt}\n\n"
        "Your invalid output (JSON parsed object):\n"
        f"{json.dumps(bad_output, ensure_ascii=False, indent=2)}\n\n"
        "Now output a corrected JSON:\n"
    )


def _default_call_model() -> CallModel:
    """
    把这里接到你现有的真实模型调用上（DeepSeek/SiliconFlow 兼容 OpenAI 的 chat/completions）。
    """
    from app.ai.deepseek_client import DeepSeekClient

    return DeepSeekClient
