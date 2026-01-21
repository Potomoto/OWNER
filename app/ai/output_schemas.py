from pydantic import BaseModel, Field


# 省略号表示必填字段
# Summary：摘要+要点
class SummaryOut(BaseModel):
    summary: str = Field(..., description="1-3 sentences summary")
    bullets: list[str] = Field(default_factory=list, description="Key bullet points (0-5)")


# Rewrite：改写文本+风格
class RewriteOut(BaseModel):
    rewritten: str = Field(..., description="Rewritten text")
    style: str = Field(..., description="Rewrite style label")


# QA：答案+引用
class QAOut(BaseModel):
    answer: str = Field(..., description="Direct answer")
    citations: list[str] = Field(
        default_factory=list, description="References (ids/urls/notes) if any"
    )
