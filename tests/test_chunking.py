import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.rag.chunk_service import upsert_note_chunks
from app.ai.rag.chunking import ChunkConfig, split_text
from app.db import Base
from app.models import Note, NoteChunk  # noqa: F401（确保 NoteChunk 被导入注册到 Base）


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "chunking_test.db"
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


def test_split_text_basic():
    text = "A" * 50 + "。 " + "B" * 50
    chunks = split_text(text, ChunkConfig(chunk_size=60, overlap=10))
    assert len(chunks) >= 2
    assert all(isinstance(c, str) and c.strip() for c in chunks)


def test_upsert_note_chunks_delete_and_recreate(db_session):
    # 1) create note
    note = Note(title="demo", content="第一段。" + "A" * 120 + "\n\n第二段。" + "B" * 120)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    # 2) upsert chunks
    r1 = upsert_note_chunks(db_session, note.id)
    assert r1["chunks"] > 0

    c1 = (
        db_session.query(NoteChunk)
        .filter(NoteChunk.note_id == note.id)
        .order_by(NoteChunk.chunk_index)
        .all()
    )
    assert len(c1) == r1["chunks"]
    assert [x.chunk_index for x in c1] == list(range(len(c1)))

    # 3) update note content -> upsert again (should replace chunks)
    note.content = "新内容。" + "C" * 300
    db_session.commit()

    r2 = upsert_note_chunks(db_session, note.id)
    c2 = db_session.query(NoteChunk).filter(NoteChunk.note_id == note.id).all()
    assert len(c2) == r2["chunks"]
