from datetime import datetime

from pydantic import BaseModel

# pydantic是FastAPI的数据校验器和数据模型


# 规定“创建笔记时用户必须传什么(title和content)
class NoteCreate(BaseModel):
    title: str
    content: str


# 规定“我们给用户返回的笔记长什么样(id\title\content\created_at)
class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
