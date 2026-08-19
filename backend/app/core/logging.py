"""统一日志配置（占位，后续接入结构化日志 + LangSmith）。"""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """配置根日志。"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )