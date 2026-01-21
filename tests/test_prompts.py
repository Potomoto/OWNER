import pytest

from app.ai.prompt_render import render_prompt


def test_prompt_render_basic():
    # 只要能把占位符替换成功就算通过
    text = render_prompt("summarize_v1", content="hello")
    assert "hello" in text


def test_prompt_render_summarize_requires_chinese():
    text = render_prompt("summarize_v1", content="hello world")
    assert "hello world" in text
    assert "Simplified Chinese" in text
    assert "Output JSON only" in text


def test_prompt_render_rewrite_requires_chinese():
    text = render_prompt("rewrite_v1", content="hello", style="formal")
    assert "hello" in text
    assert "formal" in text
    assert "Simplified Chinese" in text
    assert "Output JSON only" in text


def test_prompt_render_missing_placeholder_gives_friendly_error():
    # rewrite_v1 需要 content 和 style；这里只给 content，故应报错
    with pytest.raises(ValueError) as excinfo:
        render_prompt("rewrite_v1", content="hello")
    msg = str(excinfo.value)
    assert "Missing placeholder" in msg
    assert "rewrite_v1" in msg
    assert "style" in msg
