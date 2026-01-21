from pathlib import Path

from app.ai.prompt_registry import PROMPTS


def load_prompt(prompt_key: str) -> str:
    spec = PROMPTS[prompt_key]
    return Path(spec.path).read_text(encoding="utf-8")


def render_prompt(prompt_key: str, **kwargs) -> str:
    template = load_prompt(prompt_key)
    # 最简单的渲染：str.format
    return template.format(**kwargs)
