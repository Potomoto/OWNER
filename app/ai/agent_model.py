from __future__ import annotations

from typing import Awaitable, Callable

from app import settings
from app.ai.deepseek_client import DeepSeekClient

# 统一一个签名：输入 prompt 字符串，输出 dict（已解析 JSON）
CallModel = Callable[[str], Awaitable[dict]]


def get_agent_call_model() -> CallModel:
    """
    FastAPI dependency：提供一个“真实模型调用函数”。

    为什么返回函数而不是返回 client？
    - 你在 stepper/agent 里只关心 call_model(prompt)->dict
    - 这样测试时更容易替换（override 成 fake_model）
    """
    client = DeepSeekClient(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        timeout_s=30.0,
    )

    async def _call(prompt: str) -> dict:
        # 这里统一把“决策型任务”的参数固定住：
        # - 温度低：更稳、更少胡说
        # - max_tokens 适中：避免输出太长
        return await client.chat_json(
            prompt,
            system_prompt="You are a helpful assistant. Output JSON only.",
            max_tokens=600,
            temperature=0.1,
        )

    return _call
