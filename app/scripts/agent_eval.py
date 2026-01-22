import argparse
import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import settings
from app.ai.deepseek_client import DeepSeekClient

# 你的 Session19 代码：
# run_react_agent(db=..., request=..., call_model=..., max_steps=..., prompt_key=...)
from app.ai.react_agent import run_react_agent  # noqa: E402

load_dotenv()


def load_jsonl(path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
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


def sqlite_file_from_url(url: str) -> Optional[Path]:
    """
    仅支持 sqlite:///xxx.db 这种形式，返回 db 文件路径。
    """
    if not url.startswith("sqlite:///"):
        return None
    p = url.replace("sqlite:///", "", 1)
    return Path(p)


def make_session_from_sqlite_file(db_file: Path):
    """
    给指定 sqlite 文件创建一个独立 engine/sessionmaker（不污染 app.db 的全局 engine）。
    """
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal


def build_real_call_model():
    """
    返回一个 async call_model(prompt)->dict
    """
    api_key = os.getenv("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
    base_url = os.getenv(
        "DEEPSEEK_BASE_URL", getattr(settings, "DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1")
    )
    model = os.getenv(
        "DEEPSEEK_MODEL",
        getattr(settings, "DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"),
    )

    client = DeepSeekClient(api_key=api_key, base_url=base_url, model=model, timeout_s=60.0)

    async def _call(prompt: str) -> dict:
        return await client.chat_json(
            prompt,
            system_prompt=(
                "You are a helpful assistant. "
                "Output MUST be valid JSON only. "
                "All JSON string values MUST be in Simplified Chinese."
            ),
            temperature=0.1,
            max_tokens=700,
            retry_on_empty=1,
        )

    return _call


def build_stub_call_model():
    """
    仅用于验证脚本管线（不用于真实 A/B 优劣判断）
    - 第一次输出 tool(create_note)
    - 第二次输出 final
    """
    calls = {"n": 0}

    async def _call(prompt: str) -> dict:
        calls["n"] += 1
        if calls["n"] % 2 == 1:
            return {
                "type": "tool",
                "tool_name": "create_note",
                "args": {"title": "t", "content": "c"},
            }
        return {"type": "final", "answer": "（stub）已完成", "citations": []}

    return _call


@dataclass
class Metrics:
    total: int = 0
    success: int = 0  # stopped_reason == final
    max_steps: int = 0
    exceptions: int = 0

    total_steps: int = 0
    total_cost_ms: float = 0.0

    tool_calls: int = 0
    tool_errors: int = 0

    chinese_ok: int = 0

    expected_tool_cases: int = 0
    expected_tool_hits: int = 0  # expected_tools ⊆ actual_tools


def extract_tool_names(steps: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for s in steps:
        act = s.get("action") or {}
        tn = act.get("tool_name")
        if tn:
            names.append(str(tn))
    return names


def expected_tools_hit(expected: list[str], actual: list[str]) -> bool:
    """
    简单标准：expected 列表中的工具名都出现在 actual 里（不强制顺序）。
    新手阶段先用这个，后面再升级成“顺序/次数”更严格的判定。
    """
    if not expected:
        return True
    aset = set(actual)
    return all(t in aset for t in expected)


async def run_one(
    *,
    item: dict[str, Any],
    prompt_key: str,
    call_model,
    base_sqlite_file: Path,
    tmp_db_file: Path,
    max_steps: int,
) -> dict[str, Any]:
    """
    为了公平 A/B：每条样本都从同一个 base DB copy 出一个 tmp DB 来跑，避免状态相互污染。
    """
    shutil.copyfile(base_sqlite_file, tmp_db_file)
    SessionLocal = make_session_from_sqlite_file(tmp_db_file)

    db = SessionLocal()
    try:
        req = item["request"]
        result = await run_react_agent(
            db=db,
            request=req,
            call_model=call_model,
            max_steps=max_steps,
            prompt_key=prompt_key,
        )
        # result 可能是 Pydantic model，也可能是 dict
        if hasattr(result, "model_dump"):
            out = result.model_dump()
        else:
            out = dict(result)

        out_row = {
            "id": item.get("id"),
            "request": req,
            "expected_tools": item.get("expected_tools", []),
            "prompt_key": prompt_key,
            "result": out,
        }
        return out_row

    finally:
        db.close()
        # tmp db 你可以保留用于排查；这里先不删，方便 debug
        # tmp_db_file.unlink(missing_ok=True)


def update_metrics(m: Metrics, row: dict[str, Any]) -> None:
    m.total += 1

    out = row["result"]
    stopped = out.get("stopped_reason", "")
    steps = out.get("steps", [])
    answer = out.get("answer", "") or ""
    cost_ms = float(out.get("cost_ms", 0.0) or 0.0)

    if stopped == "final":
        m.success += 1
    elif stopped == "max_steps":
        m.max_steps += 1

    m.total_steps += len(steps)
    m.total_cost_ms += cost_ms

    if looks_chinese(answer):
        m.chinese_ok += 1

    # 工具错误率
    for s in steps:
        obs = s.get("observation") or {}
        if "ok" in obs:
            m.tool_calls += 1
            if not obs.get("ok", False):
                m.tool_errors += 1

    expected = row.get("expected_tools") or []
    actual_tools = extract_tool_names(steps)
    if expected:
        m.expected_tool_cases += 1
        if expected_tools_hit(expected, actual_tools):
            m.expected_tool_hits += 1


def metrics_to_dict(m: Metrics) -> dict[str, Any]:
    total = m.total or 1
    tool_calls = m.tool_calls or 1
    expected_cases = m.expected_tool_cases or 1

    return {
        "total": m.total,
        "success_rate": m.success / total,
        "max_steps_rate": m.max_steps / total,
        "exception_rate": m.exceptions / total,
        "avg_steps": m.total_steps / total,
        "avg_cost_ms": m.total_cost_ms / total,
        "tool_error_rate": m.tool_errors / tool_calls,
        "chinese_rate": m.chinese_ok / total,
        "expected_tool_match_rate": m.expected_tool_hits / expected_cases
        if m.expected_tool_cases
        else None,
        "counts": {
            "success": m.success,
            "max_steps": m.max_steps,
            "exceptions": m.exceptions,
            "tool_calls": m.tool_calls,
            "tool_errors": m.tool_errors,
            "expected_cases": m.expected_tool_cases,
        },
    }


async def evaluate_variant(
    *,
    items: list[dict[str, Any]],
    prompt_key: str,
    mode: str,
    out_dir: Path,
    base_sqlite_file: Path,
    max_steps: int,
    limit: Optional[int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if mode == "stub":
        call_model = build_stub_call_model()
    else:
        call_model = build_real_call_model()

    rows: list[dict[str, Any]] = []
    m = Metrics()

    use_items = items[:limit] if limit else items

    for it in use_items:
        tmp_db_file = out_dir / "tmp_db" / f"{prompt_key}_case_{it.get('id')}.db"
        tmp_db_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            row = await run_one(
                item=it,
                prompt_key=prompt_key,
                call_model=call_model,
                base_sqlite_file=base_sqlite_file,
                tmp_db_file=tmp_db_file,
                max_steps=max_steps,
            )
            rows.append(row)
            update_metrics(m, row)
        except Exception as e:
            m.total += 1
            m.exceptions += 1
            rows.append(
                {
                    "id": it.get("id"),
                    "request": it.get("request"),
                    "expected_tools": it.get("expected_tools", []),
                    "prompt_key": prompt_key,
                    "error": str(e)[:300],
                }
            )

    return rows, metrics_to_dict(m)


async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="app/scripts/data/agent_requests.jsonl")
    parser.add_argument("--mode", choices=["stub", "real"], default="real")
    parser.add_argument("--prompt_a", default="react_step_v1")
    parser.add_argument("--prompt_b", default="react_step_v1b")
    parser.add_argument("--max_steps", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="Limit cases (0 means no limit)")
    args = parser.parse_args()

    items = load_jsonl(args.data)

    # ✅ 为了评测不污染你的开发库：复制一份 base DB 作为“评测基准库”
    base_db_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    base_sqlite = sqlite_file_from_url(base_db_url)
    if base_sqlite is None:
        raise RuntimeError("Session20 脚本目前只支持 sqlite:///... 的 DATABASE_URL")

    if not base_sqlite.exists():
        raise RuntimeError(f"Base sqlite file not found: {base_sqlite}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / f"agent_ab_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 固定一份“评测基准库”（两个 variant 都从这份 copy）
    base_eval_db = out_dir / "base_eval.db"
    shutil.copyfile(base_sqlite, base_eval_db)

    limit = args.limit if args.limit > 0 else None

    rows_a, metrics_a = await evaluate_variant(
        items=items,
        prompt_key=args.prompt_a,
        mode=args.mode,
        out_dir=out_dir,
        base_sqlite_file=base_eval_db,
        max_steps=args.max_steps,
        limit=limit,
    )

    rows_b, metrics_b = await evaluate_variant(
        items=items,
        prompt_key=args.prompt_b,
        mode=args.mode,
        out_dir=out_dir,
        base_sqlite_file=base_eval_db,
        max_steps=args.max_steps,
        limit=limit,
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


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
