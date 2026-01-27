from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# Note代表一张数据库表
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ✅ 可选但推荐：一条 Note 对应多个 Chunk
    # - cascade="all, delete-orphan"：
    # - - 当 note 被删时，chunks 也会被 ORM 级联删除（前提：你通过 ORM 删除）
    # - order_by：取 chunks 时自动按 chunk_index 排序
    # - relationship 反向关系：Note 里有多个 NoteChunk
    chunks: Mapped[list["NoteChunk"]] = relationship(
        back_populates="note",
        cascade="all, delete-orphan",
        order_by="NoteChunk.chunk_index",
    )


class NoteChunk(Base):
    """
    NoteChunk：把一条 Note 切分成多个可检索单元（chunk）。
    未来会对每个 chunk 做 embedding 并写入向量库（Chroma），用于 RAG 检索。
    """

    __tablename__ = "note_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 外键：指向 notes.id
    # ondelete="CASCADE"：数据库级联删除（SQLite 需要启用 foreign_keys 才真正生效；我们后面可以加）
    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"),
        index=True,
    )

    # chunk_index：同一 note 内第几个 chunk，用来保持顺序与引用
    chunk_index: Mapped[int] = mapped_column(Integer)

    # chunk 的原文内容
    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 反向关系：chunk 属于哪个 note
    note: Mapped["Note"] = relationship(back_populates="chunks")

    # 表级约束：同一 note 的 chunk_index 必须唯一
    __table_args__ = (
        UniqueConstraint("note_id", "chunk_index", name="uq_note_chunks_note_id_chunk_index"),
    )
