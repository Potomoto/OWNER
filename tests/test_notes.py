from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, get_db
from app.models import Note

# 1) 测试用独立数据库（不会影响 notes.db）
TEST_DATABASE_URL = "sqlite:///./test_notes.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)

# 2) 在测试数据库里建表
Base.metadata.create_all(bind=test_engine)


# 3) 覆盖 get_db：让接口在测试时使用 test_notes.db
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# 切换生产数据库连接为测试数据库连接
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def setup_function():
    """
    每个测试前清空测试数据库，保证测试互不影响。
    """
    db = TestingSessionLocal()
    try:
        db.query(Note).delete()
        db.commit()
    finally:
        db.close()


def test_create_note():
    resp = client.post("/v1/notes", json={"title": "t1", "content": "c1"})
    assert resp.status_code == 200

    data = resp.json()
    # 不强行断言 id==1（数据库自增在不同情况下可能不重置）
    assert isinstance(data["id"], int)
    assert data["id"] > 0
    assert data["title"] == "t1"
    assert data["content"] == "c1"
    assert "created_at" in data


def test_list_notes():
    client.post("/v1/notes", json={"title": "t1", "content": "c1"})
    client.post("/v1/notes", json={"title": "t2", "content": "c2"})

    resp = client.get("/v1/notes")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 2


def test_get_note_not_found():
    resp = client.get("/v1/notes/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Note not found"


def test_update_note():
    created = client.post("/v1/notes", json={"title": "t1", "content": "c1"}).json()
    note_id = created["id"]

    resp = client.put(f"/v1/notes/{note_id}", json={"title": "t1b", "content": "c1b"})
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == note_id
    assert data["title"] == "t1b"
    assert data["content"] == "c1b"


def test_delete_note():
    created = client.post("/v1/notes", json={"title": "t1", "content": "c1"}).json()
    note_id = created["id"]

    resp = client.delete(f"/v1/notes/{note_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # 删除后再获取应 404
    resp2 = client.get(f"/v1/notes/{note_id}")
    assert resp2.status_code == 404
