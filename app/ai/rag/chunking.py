# app/ai/rag/chunking.py
from __future__ import annotations

from dataclasses import dataclass

from app import settings


@dataclass(frozen=True)
class ChunkConfig:
    chunk_size: int
    overlap: int


_DEFAULT_SEPARATORS: list[str] = [
    "\n\n",
    "\n",
    "。",  # 中文句号
    ".",  # 英文句号
    "！",
    "!",
    "？",
    "?",
    " ",  # 最后退化到空格
]


def _normalize(text: str) -> str:
    # 统一换行符，避免 Windows/Unix 差异导致切分结果不一致
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _find_breakpoint(window: str, min_idx: int) -> int | None:
    """
    在 [min_idx, len(window)) 内找一个“更自然的断点”，尽量避免硬截断。
    返回断点位置（相对于 window 的 index），找不到返回 None。

    min_idx 的意义：
    - 我们不希望断点太靠前，否则 chunk 太短、数量暴涨
    """
    best: int | None = None
    for sep in _DEFAULT_SEPARATORS:
        i = window.rfind(sep)
        if i >= min_idx:
            # 对于换行符/标点，断点放在 sep 之后更自然
            candidate = i + len(sep)
            if best is None or candidate > best:
                best = candidate
    return best


def split_text(text: str, cfg: ChunkConfig) -> list[str]:
    """
    把 text 切成若干 chunks。
    - chunk_size：每块目标长度（字符）
    - overlap：相邻 chunk 重叠的字符数（帮助检索时保留上下文连续性）

    原理：滑动窗口 + overlap
    """
    text = _normalize(text)
    if not text:
        return []

    if cfg.chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if cfg.overlap < 0:
        raise ValueError("overlap must be >= 0")
    if cfg.overlap >= cfg.chunk_size:
        raise ValueError("overlap must be < chunk_size")

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + cfg.chunk_size, n)
        window = text[start:end]

        # 如果不是最后一块，尝试在窗口内寻找更自然的断点
        if end < n:
            # 不要断得太早：至少保留 60% 的目标长度
            min_idx = int(cfg.chunk_size * 0.6)
            bp = _find_breakpoint(window, min_idx=min_idx)
            if bp is not None and bp > 0:
                end = start + bp
                window = text[start:end]

        chunk = window.strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break

        # 下一块从 end-overlap 开始（但必须保证推进，否则会死循环）
        next_start = end - cfg.overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def split_note(content: str) -> list[str]:
    """
    供业务层直接调用：从 settings 读取 chunk 配置。
    """
    cfg = ChunkConfig(
        chunk_size=settings.RAG_CHUNK_SIZE,
        overlap=settings.RAG_CHUNK_OVERLAP,
    )
    return split_text(content, cfg)
