from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.notes import NoteCreate, NoteOut
from app.security import verify_api_key
from app.services.notes_service import NotesService

# 给整个router加入鉴权依赖
router = APIRouter(dependencies=[Depends(verify_api_key)])
service = NotesService()


# Depends(get_db)是FastAPI的依赖注入，会自动执行get_db()，返回一个可用的session，并在结束时自动关闭
@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    return service.create(db, payload)


# 规定单次获取的数量、起点的下限
@router.get("/notes", response_model=list[NoteOut])
def list_notes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at_desc"),
    db: Session = Depends(get_db),
):
    return service.list(db, limit=limit, offset=offset, sort=sort)


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int, db: Session = Depends(get_db)):
    return service.get(db, note_id)


@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteCreate, db: Session = Depends(get_db)):
    return service.update(db, note_id, payload)


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    service.delete(db, note_id)
    return {"deleted": True}
