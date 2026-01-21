from pathlib import Path

from app.ai.prompt_registry import PROMPTS


def load_prompt(prompt_key: str) -> str:
    spec = PROMPTS[prompt_key]
    return Path(spec.path).read_text(encoding="utf-8")


def render_prompt(prompt_key: str, **kwargs) -> str:
    template = load_prompt(prompt_key)
    try:
        return template.format(**kwargs)
    except KeyError as e:
        missing = e.args[0]
        raise ValueError(
            f"Missing placeholder '{missing}' when rendering prompt '{prompt_key}'. "
            f"Provided keys: {sorted(kwargs.keys())}"
        ) from e
