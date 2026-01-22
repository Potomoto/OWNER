import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.tools.registry import run_tool
from app.db import Base
from app.models import Note  # noqa: F401  (确保模型被导入，Base.metadata 才有表定义)


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "tools_test.db"
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


def test_unknown_tool(db_session):
    r = run_tool(db_session, "not_exists", {})
    assert r["ok"] is False
    assert r["error"]["code"] == "unknown_tool"


def test_create_get_search_update_delete(db_session):
    # create
    r1 = run_tool(db_session, "create_note", {"title": "OKR", "content": "完成 Session17 工具层"})
    assert r1["ok"] is True
    note_id = r1["data"]["note"]["id"]
    assert isinstance(note_id, int) and note_id > 0

    # get
    r2 = run_tool(db_session, "get_note", {"note_id": note_id})
    assert r2["ok"] is True
    assert r2["data"]["note"]["title"] == "OKR"

    # search
    r3 = run_tool(db_session, "search_notes", {"query": "OKR", "limit": 5})
    assert r3["ok"] is True
    ids = [x["id"] for x in r3["data"]["results"]]
    assert note_id in ids

    # update (partial)
    r4 = run_tool(db_session, "update_note", {"note_id": note_id, "content": "已完成，并补了测试"})
    assert r4["ok"] is True
    assert r4["data"]["note"]["content"] == "已完成，并补了测试"

    # delete
    r5 = run_tool(db_session, "delete_note", {"note_id": note_id})
    assert r5["ok"] is True
    assert r5["data"]["deleted"] is True

    # get again -> not_found (来自 NotesService.get 的 HTTPException，被 run_tool 转成稳定错误)
    r6 = run_tool(db_session, "get_note", {"note_id": note_id})
    assert r6["ok"] is False
    assert r6["error"]["code"] in {"not_found", "http_error"}
