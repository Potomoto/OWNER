# app/core/logging.py
import logging
import sys
from app import settings


def setup_logging() -> None:
    """
    配置日志：
    - 输出到 stdout（容器/云平台会收集 stdout）
    - 简单清晰：时间 + 等级 + 信息
    """
    # stdout是云平台/容器的标准日志出口
    level_name = getattr(settings, "LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
