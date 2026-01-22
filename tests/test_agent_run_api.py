from fastapi.testclient import TestClient

from app.ai.agent_model import get_agent_call_model
from app.main import app

HEADERS = {"X-API-Key": "test-key"}


def test_agent_run_api_with_fake_model():
    """
    测试目标：
    - 不调用真实模型
    - 走完整 endpoint
    - 能执行至少一个工具（create_note）
    """

    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        # 第 1 步：调用 create_note
        if calls["n"] == 1:
            return {
                "type": "tool",
                "tool_name": "create_note",
                "args": {"title": "t", "content": "c"},
            }
        # 第 2 步：结束
        return {"type": "final", "answer": "已创建笔记", "citations": []}

    # ✅ 覆盖模型依赖：让 endpoint 用 fake_model
    app.dependency_overrides[get_agent_call_model] = lambda: fake_model

    client = TestClient(app)
    resp = client.post(
        "/ai/agent/run",
        json={"request": "创建一条笔记", "max_steps": 3, "debug": True},
        headers=HEADERS,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "已创建笔记"
    assert data["stopped_reason"] == "final"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["action"]["tool_name"] == "create_note"
    assert data["steps"][0]["observation"]["ok"] is True

    # 清理 override（避免影响其他测试）
    app.dependency_overrides.pop(get_agent_call_model, None)
