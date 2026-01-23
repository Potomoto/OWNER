import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.tools.langchain_adapter import build_langchain_tools
from app.db import Base
from app.models import Note  # noqa: F401 (确保表注册)


# fixture: 设置一个临时的 SQLite 数据库用于测试
@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "langchain_tools_test.db"
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


def test_langchain_tools_invoke_create(db_session):
    tools = build_langchain_tools(db_session)
    by_name = {t.name: t for t in tools}

    assert "create_note" in by_name

    out = by_name["create_note"].invoke({"title": "t", "content": "c"})
    # 我们工具返回的是 run_tool 的统一结构：ok/tool_name/data/error
    assert out["ok"] is True
    assert out["tool_name"] == "create_note"
    assert out["data"]["note"]["title"] == "t"
