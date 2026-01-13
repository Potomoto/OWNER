from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.notes import NoteCreate, NoteOut
from app.services.notes_service import NotesService

router = APIRouter()
service = NotesService()

# Depends(get_db)是FastAPI的依赖注入，会自动执行get_db()，返回一个可用的session，并在结束时自动关闭
@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    return service.create(db, payload)


@router.get("/notes", response_model=list[NoteOut])
def list_notes(db: Session = Depends(get_db)):
    return service.list(db)


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
