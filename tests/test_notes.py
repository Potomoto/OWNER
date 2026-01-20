import os
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models import Note

os.environ["API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite:///./test_notes.db"  # 新增：避免生成 notes.db

HEADERS = {"X-API-Key": "test-key"}

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
    resp = client.post("/v1/notes", json={"title": "t1", "content": "c1"}, headers=HEADERS)
    assert resp.status_code == 200

    data = resp.json()
    # 不强行断言 id==1（数据库自增在不同情况下可能不重置）
    assert isinstance(data["id"], int)
    assert data["id"] > 0
    assert data["title"] == "t1"
    assert data["content"] == "c1"
    assert "created_at" in data


def test_list_notes():
    client.post("/v1/notes", json={"title": "t1", "content": "c1"}, headers=HEADERS)
    client.post("/v1/notes", json={"title": "t2", "content": "c2"}, headers=HEADERS)

    resp = client.get("/v1/notes", headers=HEADERS)
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 2


def test_get_note_not_found():
    resp = client.get("/v1/notes/999", headers=HEADERS)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Note not found"


def test_update_note():
    created = client.post(
        "/v1/notes", json={"title": "t1", "content": "c1"}, headers=HEADERS
    ).json()
    note_id = created["id"]

    resp = client.put(
        f"/v1/notes/{note_id}", json={"title": "t1b", "content": "c1b"}, headers=HEADERS
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == note_id
    assert data["title"] == "t1b"
    assert data["content"] == "c1b"


def test_delete_note():
    created = client.post(
        "/v1/notes", json={"title": "t1", "content": "c1"}, headers=HEADERS
    ).json()
    note_id = created["id"]

    resp = client.delete(f"/v1/notes/{note_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # 删除后再获取应 404
    resp2 = client.get(f"/v1/notes/{note_id}", headers=HEADERS)
    assert resp2.status_code == 404


def _iso_to_dt(s: str) -> datetime:
    # created_at 是 ISO 字符串，比如 "2026-01-14T12:34:56.123456"
    return datetime.fromisoformat(s)


def test_list_notes_pagination_limit_offset():
    client.post("/v1/notes", json={"title": "a", "content": "1"}, headers=HEADERS)
    client.post("/v1/notes", json={"title": "b", "content": "2"}, headers=HEADERS)
    client.post("/v1/notes", json={"title": "c", "content": "3"}, headers=HEADERS)

    r1 = client.get("/v1/notes?limit=1&offset=0", headers=HEADERS)
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1) == 1

    r2 = client.get("/v1/notes?limit=1&offset=1", headers=HEADERS)
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2) == 1

    # 两页拿到的 title 应该不同（证明 offset 生效）
    assert d1[0]["title"] != d2[0]["title"]


def test_list_notes_sort_created_at_asc_desc():
    client.post("/v1/notes", json={"title": "first", "content": "1"}, headers=HEADERS)
    client.post("/v1/notes", json={"title": "second", "content": "2"}, headers=HEADERS)

    r_desc = client.get("/v1/notes?limit=2&sort=created_at_desc", headers=HEADERS)
    assert r_desc.status_code == 200
    d_desc = r_desc.json()
    assert len(d_desc) == 2
    assert _iso_to_dt(d_desc[0]["created_at"]) >= _iso_to_dt(d_desc[1]["created_at"])

    r_asc = client.get("/v1/notes?limit=2&sort=created_at_asc", headers=HEADERS)
    assert r_asc.status_code == 200
    d_asc = r_asc.json()
    assert len(d_asc) == 2
    assert _iso_to_dt(d_asc[0]["created_at"]) <= _iso_to_dt(d_asc[1]["created_at"])
