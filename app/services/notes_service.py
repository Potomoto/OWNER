from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

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

    # 对获取的结果进行分页（20条/页，并进行排序）
    def list(self, db: Session, limit: int = 20, offset: int = 0, sort: str = "created_at_desc") -> list[NoteOut]:
        # 1) 排序字段白名单（避免乱传）
        # 首先按照场景时间排序，再使用id作为第二排序
        if sort == "created_at_desc":
            order_clause = [desc(Note.created_at), desc(Note.id)]
        elif sort == "created_at_asc":
            order_clause = [asc(Note.created_at), asc(Note.id)]
        else:
            raise HTTPException(status_code=400, detail="Invalid sort. Use created_at_desc or created_at_asc")

        # 2) 查询 + 排序 + 分页
        q = (
            db.query(Note)
            .order_by(*order_clause)
            .offset(offset)
            .limit(limit)
        )
        notes = q.all()

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
