from app.ai.output_schemas import SummaryOut
from app.ai.prompt_render import render_prompt


def test_prompt_render_basic():
    # 只要能把占位符替换成功就算通过
    text = render_prompt("summarize_v1", content="hello")
    assert "hello" in text


def test_schema_validation():
    out = SummaryOut(summary="ok", bullets=["a", "b"])
    assert out.summary == "ok"
