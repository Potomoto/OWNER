import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import settings
from app.ai.langgraph_agent import run_langgraph_agent


async def main():
    # DB session（用你的 DATABASE_URL）
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
        if settings.DATABASE_URL.startswith("sqlite")
        else {},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = SessionLocal()
    try:
        calls = {"n": 0}

        async def fake_model(prompt: str):
            calls["n"] += 1
            # 第 1 步：调用 create_note
            if calls["n"] == 1:
                return {
                    "type": "tool",
                    "tool_name": "create_note",
                    "args": {"title": "LG", "content": "hello"},
                }
            # 第 2 步：final
            return {"type": "final", "answer": "已创建笔记并结束。", "citations": []}

        result = await run_langgraph_agent(
            db=db,
            request="创建一条标题为LG的笔记，然后结束",
            call_model=fake_model,
            max_steps=5,
            prompt_key="react_step_v1",
        )

        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        assert len(result.steps) >= 1, "验收失败：没有执行 tool 节点"

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
