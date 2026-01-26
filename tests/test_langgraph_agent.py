import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.langgraph_agent import build_langgraph_agent
from app.db import Base
from app.models import Note  # noqa: F401


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "langgraph_mem_test.db"
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
async def test_tool_then_final(db_session):
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

    saver = InMemorySaver()
    app = build_langgraph_agent(
        db=db_session,
        call_model=fake_model,
        checkpointer=saver,
        max_steps=5,
        memory_max_steps=20,
    )

    config = {"configurable": {"thread_id": "t1"}}
    state = await app.ainvoke({"request": "创建一条笔记然后结束"}, config)

    steps = state.get("steps") or []
    assert len(steps) == 1
    assert steps[0]["action"]["tool_name"] == "create_note"
    assert steps[0]["observation"]["ok"] is True
    assert state.get("answer") == "已创建并结束"


@pytest.mark.anyio
async def test_same_thread_id_can_continue(db_session):
    async def fake_model_1(prompt: str):
        # 第一次：tool -> final
        if '"steps"' in prompt:
            pass
        return {"type": "tool", "tool_name": "create_note", "args": {"title": "a", "content": "b"}}

    async def fake_model_2(prompt: str):
        return {"type": "final", "answer": "第二轮结束", "citations": []}

    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "t2"}}

    # 第一次：我们用一个模型让它先 tool 再 final（用两次 invoke 模拟两轮对话更直观）
    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "type": "tool",
                "tool_name": "create_note",
                "args": {"title": "a", "content": "b"},
            }
        return {"type": "final", "answer": "第一轮结束", "citations": []}

    app = build_langgraph_agent(
        db=db_session,
        call_model=fake_model,
        checkpointer=saver,
        max_steps=5,
        memory_max_steps=20,
    )

    state1 = await app.ainvoke({"request": "第一轮：创建笔记"}, config)
    assert len(state1.get("steps") or []) == 1

    # 第二次：换一个模型（模拟“服务重启/模型实现变化”），但 thread_id 相同，应能带入历史 steps
    app2 = build_langgraph_agent(
        db=db_session,
        call_model=fake_model_2,
        checkpointer=saver,
        max_steps=5,
        memory_max_steps=20,
    )
    state2 = await app2.ainvoke({"request": "第二轮：直接结束"}, config)
    assert len(state2.get("steps") or []) >= 1
    assert state2.get("answer") == "第二轮结束"


@pytest.mark.anyio
async def test_memory_trim_to_last_20(db_session):
    # 连续输出 25 次 tool，最后 final，验证 steps 被裁剪到 20
    calls = {"n": 0}

    async def fake_model(prompt: str):
        calls["n"] += 1
        if calls["n"] <= 25:
            return {
                "type": "tool",
                "tool_name": "create_note",
                "args": {"title": f"t{calls['n']}", "content": "c"},
            }
        return {"type": "final", "answer": "done", "citations": []}

    saver = InMemorySaver()
    app = build_langgraph_agent(
        db=db_session,
        call_model=fake_model,
        checkpointer=saver,
        max_steps=30,
        memory_max_steps=20,
    )

    config = {"configurable": {"thread_id": "t3"}}
    state = await app.ainvoke({"request": "批量创建很多笔记然后结束"}, config)

    steps = state.get("steps") or []
    assert len(steps) == 20
    assert state.get("answer") == "done"
