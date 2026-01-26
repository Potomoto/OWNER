from __future__ import annotations

from dataclasses import dataclass

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@dataclass
class AsyncSqliteCheckpointerHandle:
    saver: AsyncSqliteSaver
    conn: aiosqlite.Connection


async def make_async_sqlite_saver(db_path: str) -> AsyncSqliteCheckpointerHandle:
    """
    为 LangGraph 创建一个 SQLite checkpointer。

    重要：不要用 `with sqlite3.connect(...) as conn`，
    因为 conn 离开 with 会关闭，后续 graph 可能报 “closed database”。
    这个坑在 LangGraph issue 里有人踩过。
    """
    conn = await aiosqlite.connect(db_path)
    saver = AsyncSqliteSaver(conn)
    return AsyncSqliteCheckpointerHandle(saver=saver, conn=conn)
