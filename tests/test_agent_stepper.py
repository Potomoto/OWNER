import pytest

from app.ai.agent_schemas import FinalAnswer, ToolCall
from app.ai.agent_stepper import decide_next_action


@pytest.mark.anyio
async def test_decide_tool_ok():
    async def fake_model(prompt: str):
        return {"type": "tool", "tool_name": "search_notes", "args": {"query": "OKR", "limit": 5}}

    action = await decide_next_action(request="查一下OKR", steps=[], call_model=fake_model)
    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_notes"
    assert action.args["query"] == "OKR"


@pytest.mark.anyio
async def test_decide_final_ok():
    async def fake_model(prompt: str):
        return {"type": "final", "answer": "好的，我已完成。", "citations": ["note:1"]}

    action = await decide_next_action(request="直接回答", steps=[], call_model=fake_model)
    assert isinstance(action, FinalAnswer)
    assert "完成" in action.answer


@pytest.mark.anyio
async def test_decide_retry_on_invalid_tool_then_fix():
    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        if calls["n"] == 1:
            # 第一次：模型瞎编工具名（应触发 retry）
            return {"type": "tool", "tool_name": "search_notez", "args": {"query": "OKR"}}
        # 第二次：修正
        return {"type": "tool", "tool_name": "search_notes", "args": {"query": "OKR", "limit": 5}}

    action = await decide_next_action(request="查一下OKR", steps=[], call_model=fake_model)
    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_notes"


@pytest.mark.anyio
async def test_decide_retry_on_invalid_args_then_fix():
    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        if calls["n"] == 1:
            # 第一次：limit 超范围（你 schema 里限制 le=20）
            return {
                "type": "tool",
                "tool_name": "search_notes",
                "args": {"query": "OKR", "limit": 999},
            }
        return {"type": "tool", "tool_name": "search_notes", "args": {"query": "OKR", "limit": 5}}

    action = await decide_next_action(request="查一下OKR", steps=[], call_model=fake_model)
    assert isinstance(action, ToolCall)
    assert action.args["limit"] == 5
