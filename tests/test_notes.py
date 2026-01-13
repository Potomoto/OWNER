from fastapi.testclient import TestClient
from app.main import app
from app.routers import notes as notes_router

# TestClient是一个假的浏览器/客户端，可以用代码去调用API
client = TestClient(app)


# 如果不清空，可能一些公共的数据，例如id会受到影响
def setup_function():
    """
    每个测试开始前都会运行一次。
    我们把内存数据清空，保证测试之间互不影响。
    """
    notes_router.service.clear()

# assert：断言，希望结果像后面一样，如果不是就算失败
def test_create_note():
    resp = client.post("/v1/notes", json={"title": "t1", "content": "c1"})
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == 1
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
    client.post("/v1/notes", json={"title": "t1", "content": "c1"})

    resp = client.put("/v1/notes/1", json={"title": "t1b", "content": "c1b"})
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == 1
    assert data["title"] == "t1b"
    assert data["content"] == "c1b"


def test_delete_note():
    client.post("/v1/notes", json={"title": "t1", "content": "c1"})

    resp = client.delete("/v1/notes/1")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # 删除后再获取应 404
    resp2 = client.get("/v1/notes/1")
    assert resp2.status_code == 404
