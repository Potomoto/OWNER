from fastapi import APIRouter
from app.schemas.notes import NoteCreate, NoteOut
from app.services.notes_service import NotesService

router = APIRouter()
service = NotesService()


@router.post("/notes", response_model=NoteOut)
def create_note(payload: NoteCreate):
    return service.create(payload)


@router.get("/notes", response_model=list[NoteOut])
def list_notes():
    return service.list()


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int):
    return service.get(note_id)

# 用一份新的完整数据，替换某个资源
# Put为整体替换，需要提供完整的字段，为了满足“幂等”的需求，一般更新常用put
# 幂等：同样的请求重复执行多次，结果应该一样
@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteCreate):
    return service.update(note_id, payload)


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    service.delete(note_id)
    return {"deleted": True}
