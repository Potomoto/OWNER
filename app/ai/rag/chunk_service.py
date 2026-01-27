# app/ai/rag/chunk_service.py
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai.rag.chunking import split_note
from app.models import Note, NoteChunk  # 你 Session25 已添加 NoteChunk

logger = logging.getLogger("rag.chunks")


def upsert_note_chunks(db: Session, note_id: int) -> dict[str, Any]:
    """
    为指定 note 生成 chunks，并写入 note_chunks 表。
    策略：删旧插新（稳定、简单、可回归）

    返回结构保持可读：
    {"note_id": 1, "chunks": 6, "cost_ms": 12.3}
    """
    t0 = time.perf_counter()

    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    chunks = split_note(note.content)

    # 先删旧
    # db.query(NoteChunk).filter(NoteChunk.note_id == note_id).delete(synchronize_session=False)
    db.query(NoteChunk).filter(NoteChunk.note_id == note_id).delete(synchronize_session="fetch")

    db.flush()

    # 再插新
    for i, text in enumerate(chunks):
        db.add(NoteChunk(note_id=note_id, chunk_index=i, content=text))

    db.commit()

    cost_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "upsert_note_chunks note_id=%s chunks=%s cost_ms=%.1f", note_id, len(chunks), cost_ms
    )
    return {"note_id": note_id, "chunks": len(chunks), "cost_ms": cost_ms}


def delete_note_chunks(db: Session, note_id: int) -> dict[str, Any]:
    """
    删除指定 note 的所有 chunks（后面 delete note 时会用到）。
    """
    t0 = time.perf_counter()
    n = db.query(NoteChunk).filter(NoteChunk.note_id == note_id).delete(synchronize_session=False)
    db.commit()
    cost_ms = (time.perf_counter() - t0) * 1000
    logger.info("delete_note_chunks note_id=%s deleted=%s cost_ms=%.1f", note_id, n, cost_ms)
    return {"note_id": note_id, "deleted": n, "cost_ms": cost_ms}
