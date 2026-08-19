"""GPS 教学意图结构化提取（占位）。

文档 §3.2 services/gps/reasoner.py。
"""

from pydantic import BaseModel


class TeachingIntent(BaseModel):
    """教学意图（结构化输出）。"""

    subject: str = ""
    topic: str = ""
    grade: str = ""
    duration_min: int = 0


async def extract_intent(dialogue_history: list[dict]) -> TeachingIntent:
    """占位：返回空结构，后续接入 LLM + 固定槽位。"""
    return TeachingIntent()