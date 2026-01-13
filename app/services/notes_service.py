from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Note
from app.schemas.notes import NoteCreate, NoteOut


class NotesService:
    """
    业务层：现在由 SQLite 持久化。
    每个方法接收一个 db(Session)，代表一次数据库会话。
    """

    def create(self, db: Session, payload: NoteCreate) -> NoteOut:
        note = Note(title=payload.title, content=payload.content)
        # 将对象加入本次会话
        db.add(note)
        # 将对象真正的写入到数据库中
        db.commit()
        db.refresh(note)  # 拿到自增 id 等数据库生成的字段
        return NoteOut(id=note.id, title=note.title, content=note.content, created_at=note.created_at)

    def list(self, db: Session) -> list[NoteOut]:
        notes = db.query(Note).order_by(Note.id.asc()).all()
        return [
            NoteOut(id=n.id, title=n.title, content=n.content, created_at=n.created_at)
            for n in notes
        ]

    def get(self, db: Session, note_id: int) -> NoteOut:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")
        return NoteOut(id=note.id, title=note.title, content=note.content, created_at=note.created_at)

    def update(self, db: Session, note_id: int, payload: NoteCreate) -> NoteOut:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")

        note.title = payload.title
        note.content = payload.content
        db.commit()
        db.refresh(note)
        return NoteOut(id=note.id, title=note.title, content=note.content, created_at=note.created_at)

    def delete(self, db: Session, note_id: int) -> None:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")

        db.delete(note)
        db.commit()
