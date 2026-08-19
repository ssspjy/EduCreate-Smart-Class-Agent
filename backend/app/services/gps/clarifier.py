"""GPS 固定槽位 + 动态追问 + 缺失检测（占位）。"""


async def missing_slots(intent: dict) -> list[str]:
    """占位：返回缺失的固定槽位。"""
    return []