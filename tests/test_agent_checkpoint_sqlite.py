import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.langgraph_agent import run_langgraph_agent
from app.db import Base
from app.models import Note  # noqa: F401


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "notes_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.mark.anyio
async def test_checkpoint_persists_across_runs(db_session, tmp_path):
    checkpoint_db = str(tmp_path / "agent_checkpoints.db")
    thread_id = "t1"

    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "type": "tool",
                "tool_name": "create_note",
                "args": {"title": "t", "content": "c"},
            }
        return {"type": "final", "answer": "ok", "citations": []}

    # 第一次跑：会产生 steps
    tid1, res1 = await run_langgraph_agent(
        db=db_session,
        request="创建笔记",
        call_model=fake_model,
        thread_id=thread_id,
        checkpoint_db_path=checkpoint_db,
        max_steps=3,
    )
    assert tid1 == thread_id
    assert len(res1.steps) == 1

    # 第二次跑：重新调用（同 thread_id），不应丢失之前 steps
    calls["n"] = 0

    async def fake_model2(prompt: str):
        # 直接 final，看看历史 steps 是否还在
        return {"type": "final", "answer": "ok2", "citations": []}

    tid2, res2 = await run_langgraph_agent(
        db=db_session,
        request="第二次对话",
        call_model=fake_model2,
        thread_id=thread_id,
        checkpoint_db_path=checkpoint_db,
        max_steps=3,
    )
    assert tid2 == thread_id
    assert len(res2.steps) >= 1
