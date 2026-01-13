from datetime import datetime
from fastapi import HTTPException
from app.schemas.notes import NoteCreate, NoteOut


class NotesService:
    """
    业务层：所有“笔记相关的事情”都放这里。
    目前用内存 dict 存储；未来换数据库时，主要改这里。
    """

    def __init__(self):
        self._notes: dict[int, NoteOut] = {}
        self._next_id: int = 1

    def create(self, payload: NoteCreate) -> NoteOut:
        note = NoteOut(
            id=self._next_id,
            title=payload.title,
            content=payload.content,
            created_at=datetime.utcnow(),
        )
        self._notes[self._next_id] = note
        self._next_id += 1
        return note

    def list(self) -> list[NoteOut]:
        return list(self._notes.values())

    def get(self, note_id: int) -> NoteOut:
        note = self._notes.get(note_id)
        if note is None:
            # 404：资源不存在（非常常见）
            raise HTTPException(status_code=404, detail="Note not found")
        return note

    def update(self, note_id: int, payload: NoteCreate) -> NoteOut:
        # 先确保存在，不存在就抛 404
        existing = self.get(note_id)

        updated = NoteOut(
            id=existing.id,
            title=payload.title,
            content=payload.content,
            created_at=existing.created_at,  # 保留原创建时间
        )
        self._notes[note_id] = updated
        return updated

    def delete(self, note_id: int) -> None:
        if note_id not in self._notes:
            raise HTTPException(status_code=404, detail="Note not found")
        del self._notes[note_id]

    def clear(self) -> None:
        """
        测试时会用到：清空内存数据。
        现在先放着，等第4天写测试就会用上。
        """
        self._notes.clear()
        self._next_id = 1
