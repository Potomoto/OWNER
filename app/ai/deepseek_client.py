# app/ai/deepseek_client.py
import json
import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger("ai.deepseek")


class DeepSeekClient:
    """
    只负责一件事：把 prompt 发给 DeepSeek，并拿到“模型的 content 文本”。

    设计理念（很重要）：
    - client 层不关心你的业务（摘要/改写），只关心“如何调用模型”
    - 这样未来换模型厂商，你只需要替换这个文件
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        timeout_s: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = httpx.Timeout(timeout_s)

    def _endpoint(self) -> str:
        # DeepSeek 文档：base_url 可以是 https://api.deepseek.com 或
        # https://api.deepseek.com/v1 :contentReference[oaicite:4]{index=4}
        # 我们统一拼接 /chat/completions，使两种 base_url 都可用
        return f"{self.base_url}/chat/completions"

    async def chat_json(
        self,
        user_prompt: str,
        *,
        system_prompt: str = "You are a helpful assistant. Output must be valid json.",
        max_tokens: int = 800,
        temperature: float = 0.2,
        retry_on_empty: int = 1,
    ) -> dict[str, Any]:
        """
        关键点：启用 JSON Output（response_format json_object）
        - DeepSeek 文档要求：
        - response_format + prompt 中包含 'json' + 示例
        - 我们在 system_prompt 里明确写 'json'，模板里也有 JSON 示例
        """
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        # 文档示例使用 Bearer :contentReference[oaicite:6]{index=6}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_object"
            },  # JSON mode :contentReference[oaicite:7]{index=7}
            "stream": False,
        }

        url = self._endpoint()

        for attempt in range(retry_on_empty + 1):
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
            dt_ms = (time.perf_counter() - t0) * 1000

            if resp.status_code >= 400:
                # 不把全量响应返回给用户（安全），但日志里记录关键字段
                logger.warning(
                    "DeepSeek HTTP %s (%.1fms): %s", resp.status_code, dt_ms, resp.text[:300]
                )
                raise RuntimeError(f"DeepSeek API error: HTTP {resp.status_code}")

            data = resp.json()
            content: Optional[str] = data.get("choices", [{}])[0].get("message", {}).get("content")

            # 文档提示：JSON Output 偶尔可能返回空 content
            # 需要缓解/重试 :contentReference[oaicite:8]{index=8}
            if content and content.strip():
                # JSON mode 理论上保证是合法 JSON 字符串
                # 但我们仍然 json.loads 一次做防线
                return json.loads(content)

            logger.warning(
                "DeepSeek returned empty content (attempt %s/%s)", attempt + 1, retry_on_empty + 1
            )

        raise RuntimeError("DeepSeek returned empty content")
