import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

from app.ai.output_schemas import SummaryOut
from app.ai.prompt_render import render_prompt

load_dotenv()


def load_jsonl(path: str) -> list[dict[str, Any]]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def dump_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def looks_chinese(text: str) -> bool:
    if not text:
        return False
    cn = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cn / max(len(text), 1) >= 0.2


def strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # 去掉第一行 ```json / ``` 等
        parts = s.split("\n", 1)
        s = parts[1] if len(parts) > 1 else ""
        # 去掉末尾 ```
        if s.strip().endswith("```"):
            s = s.strip()[:-3]
    return s.strip()


def extract_json_text(s: str) -> str:
    """
    兜底：如果模型没严格输出 JSON（比如前后夹杂文字），
    尝试截取第一个 { 到最后一个 } 之间的内容。
    """
    s = strip_code_fence(s)
    if not s:
        return s
    if s.lstrip().startswith("{") and s.rstrip().endswith("}"):
        return s
    la = s.find("{")
    ra = s.rfind("}")
    if la != -1 and ra != -1 and ra > la:
        return s[la : ra + 1]
    return s


def call_model_stub(prompt: str) -> str:
    return json.dumps(
        {"summary": "这是一段中文摘要。", "bullets": ["要点一", "要点二"]},
        ensure_ascii=False,
    )


def call_model_real(
    prompt: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float = 60.0,
    use_response_format: bool = True,
    retry: int = 1,
) -> str:
    """
    SiliconFlow OpenAI 兼容接口：
    POST {base_url}/chat/completions
    Header: Authorization: Bearer <API_KEY> :contentReference[oaicite:3]{index=3}

    说明：
    - use_response_format=True 会带上 response_format（SiliconFlow 文档列出了该字段）:
    - - contentReference[oaicite:4]{index=4}
    - 如果遇到 400（有些模型/网关不支持该字段），会自动降级重试一次：去掉 response_format
    """
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    url = base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. "
                    "Output MUST be valid JSON only. "
                    "All JSON string values MUST be in Simplified Chinese."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    if use_response_format:
        payload["response_format"] = {"type": "json_object"}

    last_err: Optional[str] = None

    for attempt in range(retry + 1):
        # t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(url, headers=headers, json=payload)
            # dt_ms = (time.perf_counter() - t0) * 1000

            if resp.status_code >= 400:
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                # 如果是 response_format 导致的 400，降级再试
                if use_response_format and resp.status_code == 400:
                    payload.pop("response_format", None)
                    use_response_format = False
                if attempt < retry:
                    continue
                raise RuntimeError(last_err)

            data = resp.json()
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            content = msg.get("content") or ""

            # 有些推理模型会额外带 reasoning_content，但我们只需要 content
            # （你的 prompt 要求输出 JSON，因此 content 应该就是 JSON）
            if not content.strip():
                last_err = "Empty content"
                if attempt < retry:
                    continue
                raise RuntimeError(last_err)

            # 这里返回“原始文本”，下游统一 json.loads + schema 校验
            return content

        except Exception as e:
            last_err = str(e)
            if attempt < retry:
                continue
            raise

    raise RuntimeError(last_err or "Unknown error")


def evaluate_summarize(
    items: list[dict[str, Any]],
    prompt_key: str,
    mode: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> tuple[list[dict], dict]:
    rows = []
    parse_ok = 0
    total = 0
    total_summary_len = 0
    empty_bullets = 0
    chinese_ok = 0

    for it in items:
        total += 1
        note_id = it.get("id")
        content = it.get("content", "")

        prompt = render_prompt(prompt_key, content=content)

        ok = False
        parsed = None
        err = None
        raw = ""

        try:
            if mode == "stub":
                raw = call_model_stub(prompt)
            else:
                raw = call_model_real(
                    prompt,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    temperature=0.2,
                    max_tokens=800,
                    timeout_s=90.0,
                    use_response_format=True,
                    retry=1,
                )

            raw_json_text = extract_json_text(raw)
            data = json.loads(raw_json_text)
            parsed_obj = SummaryOut.model_validate(data)
            parsed = parsed_obj.model_dump()
            ok = True

        except Exception as e:
            err = str(e)

        if ok:
            parse_ok += 1
            summary_text = parsed.get("summary", "")
            total_summary_len += len(summary_text)
            if not parsed.get("bullets"):
                empty_bullets += 1
            joined = summary_text + " " + " ".join(parsed.get("bullets", []))
            if looks_chinese(joined):
                chinese_ok += 1

        rows.append(
            {
                "note_id": note_id,
                "prompt_key": prompt_key,
                "ok": ok,
                "error": err,
                "raw": raw,
                "parsed": parsed,
            }
        )

    metrics = {
        "prompt_key": prompt_key,
        "total": total,
        "parse_success_rate": parse_ok / total if total else 0.0,
        "avg_summary_len": (total_summary_len / parse_ok) if parse_ok else 0.0,
        "empty_bullets_rate": (empty_bullets / parse_ok) if parse_ok else 0.0,
        "chinese_rate": (chinese_ok / parse_ok) if parse_ok else 0.0,
    }
    return rows, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="app/scripts/data/notes_sample.jsonl")
    parser.add_argument("--prompt_a", default="summarize_v1")
    parser.add_argument("--prompt_b", default="summarize_v1b")
    parser.add_argument("--mode", choices=["stub", "real"], default="real")
    args = parser.parse_args()

    api_key = os.getenv("DEEPSEEK_API_KEY") or ""
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")

    items = load_jsonl(args.data)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / f"ab_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_a, metrics_a = evaluate_summarize(
        items, args.prompt_a, args.mode, api_key=api_key, base_url=base_url, model=model
    )
    rows_b, metrics_b = evaluate_summarize(
        items, args.prompt_b, args.mode, api_key=api_key, base_url=base_url, model=model
    )

    dump_jsonl(str(out_dir / "A.jsonl"), rows_a)
    dump_jsonl(str(out_dir / "B.jsonl"), rows_b)

    with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump({"A": metrics_a, "B": metrics_b}, f, ensure_ascii=False, indent=2)

    print("=== A metrics ===")
    print(json.dumps(metrics_a, ensure_ascii=False, indent=2))
    print("=== B metrics ===")
    print(json.dumps(metrics_b, ensure_ascii=False, indent=2))
    print(f"\nSaved results to: {out_dir}")


if __name__ == "__main__":
    main()
