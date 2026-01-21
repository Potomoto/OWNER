# app/ai/ai_service.py
import logging
import time

from fastapi import HTTPException

from app import settings
from app.ai.deepseek_client import DeepSeekClient
from app.ai.output_schemas import RewriteOut, SummaryOut
from app.ai.prompt_registry import PROMPTS
from app.ai.prompt_render import render_prompt

logger = logging.getLogger("ai.service")


def _get_client() -> DeepSeekClient:
    return DeepSeekClient(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        timeout_s=30.0,
    )


async def summarize(content: str, prompt_key: str = "summarize_v1") -> SummaryOut:
    """
    为什么这里返回 SummaryOut（而不是 dict）？
    - 把“输出合同”贯穿整个链路：失败就报错，成功就一定结构正确
    """
    if prompt_key not in PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown prompt_key: {prompt_key}")

    prompt = render_prompt(prompt_key, content=content)

    spec = PROMPTS[prompt_key]
    t0 = time.perf_counter()

    try:
        data = await _get_client().chat_json(
            prompt,
            max_tokens=600,
            temperature=0.2,
        )
        out = SummaryOut.model_validate(data)
        return out
    except Exception as e:
        # 这里不要把 prompt 全量写日志（可能包含敏感笔记）
        logger.warning(
            "summarize failed prompt=%s/%s model=%s content_len=%s err=%s",
            spec.name,
            spec.version,
            settings.DEEPSEEK_MODEL,
            len(content or ""),
            str(e)[:200],
        )
        raise HTTPException(status_code=502, detail="Model output invalid or model call failed")
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "summarize done prompt=%s/%s model=%s content_len=%s cost=%.1fms",
            spec.name,
            spec.version,
            settings.DEEPSEEK_MODEL,
            len(content or ""),
            dt_ms,
        )


async def rewrite(content: str, style: str, prompt_key: str = "rewrite_v1") -> RewriteOut:
    if prompt_key not in PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown prompt_key: {prompt_key}")

    prompt = render_prompt(prompt_key, content=content, style=style)
    spec = PROMPTS[prompt_key]
    t0 = time.perf_counter()

    try:
        data = await _get_client().chat_json(
            prompt,
            max_tokens=1200,
            temperature=0.4,
        )
        out = RewriteOut.model_validate(data)
        return out
    except Exception as e:
        logger.warning(
            "rewrite failed prompt=%s/%s model=%s content_len=%s style=%s err=%s",
            spec.name,
            spec.version,
            settings.DEEPSEEK_MODEL,
            len(content or ""),
            style,
            str(e)[:200],
        )
        raise HTTPException(status_code=502, detail="Model output invalid or model call failed")
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "rewrite done prompt=%s/%s model=%s content_len=%s style=%s cost=%.1fms",
            spec.name,
            spec.version,
            settings.DEEPSEEK_MODEL,
            len(content or ""),
            style,
            dt_ms,
        )
