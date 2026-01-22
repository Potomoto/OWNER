# prompt注册表，告诉代码有哪些prompt、对应哪些文件、版本是什么
from dataclasses import dataclass


# dataclass是python用来轻量定义数据结构的方式
# 其中frozen=True表示不可变（防止运行时被意外修改）
@dataclass(frozen=True)
class PromptSpec:
    name: str
    version: str
    path: str


PROMPTS = {
    "summarize_v1": PromptSpec(name="summarize", version="v1", path="app/prompts/summarize_v1.txt"),
    "rewrite_v1": PromptSpec(name="rewrite", version="v1", path="app/prompts/rewrite_v1.txt"),
    "qa_v1": PromptSpec(name="qa", version="v1", path="app/prompts/qa_v1.txt"),
    "tool_select_v1": PromptSpec(
        name="tool_select", version="v1", path="app/prompts/tool_select_v1.txt"
    ),
}
PROMPTS["summarize_v1b"] = PromptSpec(
    name="summarize", version="v1b", path="app/prompts/summarize_v1b.txt"
)
PROMPTS["react_step_v1"] = PromptSpec(
    name="react_step",
    version="v1",
    path="app/prompts/react_step_v1.txt",
)
