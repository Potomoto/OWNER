from pydantic import BaseModel, Field, model_validator


# Pydantic BaseModel 用于定义 AI 工具的输入参数结构
# 能够对输入参数进行类型检查和验证
class SearchNotesArgs(BaseModel):
    query: str = Field(..., min_length=1, description="Search keyword in title/content")
    limit: int = Field(5, ge=1, le=20, description="Max number of results")


class GetNoteArgs(BaseModel):
    note_id: int = Field(..., ge=1)


class CreateNoteArgs(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class UpdateNoteArgs(BaseModel):
    note_id: int = Field(..., ge=1)
    title: str | None = Field(None, max_length=200)
    content: str | None = None

    # pydantic 验证器：要求在update时至少提供 title/content 之一
    @model_validator(mode="after")
    def _at_least_one_field(self):
        # 原理：Agent 常做“部分更新”。但如果 title/content 都没传，这次更新没有意义。
        if self.title is None and self.content is None:
            raise ValueError("At least one of title/content must be provided")
        return self


class DeleteNoteArgs(BaseModel):
    note_id: int = Field(..., ge=1)
