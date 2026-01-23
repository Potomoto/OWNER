import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.langgraph_agent import run_langgraph_agent
from app.db import Base
from app.models import Note  # noqa: F401


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "langgraph_agent_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.mark.anyio
async def test_langgraph_agent_tool_then_final(db_session):
    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "type": "tool",
                "tool_name": "create_note",
                "args": {"title": "t", "content": "c"},
            }
        return {"type": "final", "answer": "已创建并结束", "citations": []}

    out = await run_langgraph_agent(
        db=db_session,
        request="创建笔记然后结束",
        call_model=fake_model,
        max_steps=3,
        prompt_key="react_step_v1",
    )

    assert out.stopped_reason == "final"
    assert len(out.steps) == 1
    assert out.steps[0]["action"]["tool_name"] == "create_note"
    assert out.steps[0]["observation"]["ok"] is True
