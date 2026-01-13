from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.schemas.notes import NoteCreate, NoteOut

# router将所有接口都集中管理，避免混乱
# APIRouter是一个接口集合
router = APIRouter()

# 内存数据库：用 dict 存 notes
NOTES: dict[int, NoteOut] = {}
NEXT_ID = 1

# 注册一个POST接口
@router.post("/notes", response_model=NoteOut)
# 创建笔记，其中payload: NoteCreate是告诉FastAPI将请求的JSON解析成NoteCreate，并校验
def create_note(payload: NoteCreate):
    global NEXT_ID
    note = NoteOut(
        id=NEXT_ID,
        title=payload.title,
        content=payload.content,
        created_at=datetime.utcnow(),
    )
    NOTES[NEXT_ID] = note
    NEXT_ID += 1
    return note


@router.get("/notes", response_model=list[NoteOut])
def list_notes():
    return list(NOTES.values())


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int):
    note = NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    if note_id not in NOTES:
        raise HTTPException(status_code=404, detail="Note not found")
    del NOTES[note_id]
    return {"deleted": True}