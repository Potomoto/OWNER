import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ai.output_schemas import SummaryOut
from app.ai.prompt_render import render_prompt


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
    """
    粗略中文判定：只要包含一定比例的中文字符就算中文。
    原理：中文字符大多在 Unicode \u4e00-\u9fff 区间。
    """
    if not text:
        return False
    cn = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cn / max(len(text), 1) >= 0.2


def call_model_stub(prompt: str) -> str:
    """
    假模型：用于先跑通 A/B 管道。
    它返回一个“看起来像模型输出”的 JSON 字符串（中文）。
    """
    # 你也可以故意让它偶尔输出坏 JSON 来测试 parse_success_rate
    return json.dumps(
        {"summary": "这是一段中文摘要。", "bullets": ["要点一", "要点二"]},
        ensure_ascii=False,
    )


def call_model_real(prompt: str) -> str:
    """
    真实模型调用占位函数：
    - 你后面接 OpenAI/国内模型时，就在这里实现
    - 今天先别写，避免被 API/额度干扰学习节奏
    """
    raise NotImplementedError("Real model call is not implemented yet.")


def evaluate_summarize(
    items: list[dict[str, Any]], prompt_key: str, mode: str
) -> tuple[list[dict], dict]:
    rows = []
    parse_ok = 0  # 成功解析成SummaryOut的样本数
    total = 0
    total_summary_len = 0  # 成功解析样本的summary字符数累加
    empty_bullets = 0  # 成功解析但bulltes为空的计数
    chinese_ok = 0  # 成功解析且通过中文检测的计数

    for it in items:
        total += 1
        note_id = it.get("id")
        content = it.get("content", "")

        # 用prompt_key选择使用的模版（A/B）
        prompt = render_prompt(prompt_key, content=content)

        if mode == "stub":
            raw = call_model_stub(prompt)
        else:
            raw = call_model_real(prompt)

        ok = False
        parsed = None
        err = None

        try:
            data = json.loads(raw)
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
            # 中文检测：summary 与 bullets 拼一起粗略判定
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
    parser.add_argument("--mode", choices=["stub", "real"], default="stub")
    args = parser.parse_args()

    items = load_jsonl(args.data)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / f"ab_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_a, metrics_a = evaluate_summarize(items, args.prompt_a, args.mode)
    rows_b, metrics_b = evaluate_summarize(items, args.prompt_b, args.mode)

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
