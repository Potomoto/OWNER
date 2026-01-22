from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.models import Note
from app.schemas.notes import NoteCreate, NoteOut
from app.services.notes_service import NotesService

from .schemas import CreateNoteArgs, DeleteNoteArgs, GetNoteArgs, SearchNotesArgs, UpdateNoteArgs

service = NotesService()


def _note_to_json(note: NoteOut) -> dict:
    # Pydantic v2: model_dump(mode="json") 会把 datetime 转成 ISO 字符串，确保可 JSON 序列化
    return note.model_dump(mode="json")


def search_notes(db: Session, args: SearchNotesArgs) -> dict:
    """
    关键词搜索：在 title/content 做 contains
    返回短结果（id/title/snippet），避免把整篇 content 塞回模型导致上下文爆炸。
    """
    q = args.query.strip()
    rows = (
        db.query(Note)
        .filter(or_(Note.title.contains(q), Note.content.contains(q)))
        .order_by(desc(Note.created_at), desc(Note.id))
        .limit(args.limit)
        .all()
    )
    # snippet 只取 content 前 120 字符
    results = [{"id": n.id, "title": n.title, "snippet": (n.content or "")[:120]} for n in rows]
    return {"results": results}


def get_note(db: Session, args: GetNoteArgs) -> dict:
    # 复用你已有的 NotesService（404 行为与现有接口一致）
    out = service.get(db, args.note_id)
    return {"note": _note_to_json(out)}


def create_note(db: Session, args: CreateNoteArgs) -> dict:
    payload = NoteCreate(title=args.title, content=args.content)
    out = service.create(db, payload)
    return {"note": _note_to_json(out)}


def update_note(db: Session, args: UpdateNoteArgs) -> dict:
    """
    Agent 常需要“部分更新”，但你现有 NotesService.update 是全量更新。
    所以这里用 ORM 直接做 patch：只改用户传入的字段。
    """
    note = db.query(Note).filter(Note.id == args.note_id).first()
    if note is None:
        # 这里不抛 HTTPException 也可以，但你后面会在 run_tool 统一捕获异常。
        # 这里直接返回“业务型错误”，更适合 agent 继续调整策略。
        return {
            "error": {
                "code": "not_found",
                "message": "Note not found",
                "details": {"note_id": args.note_id},
            }
        }

    if args.title is not None:
        note.title = args.title
    if args.content is not None:
        note.content = args.content

    db.commit()
    db.refresh(note)

    out = NoteOut(id=note.id, title=note.title, content=note.content, created_at=note.created_at)
    return {"note": _note_to_json(out)}


def delete_note(db: Session, args: DeleteNoteArgs) -> dict:
    # 复用 service.delete（行为与 /v1/notes/{id} 保持一致）
    service.delete(db, args.note_id)
    return {"deleted": True, "note_id": args.note_id}
