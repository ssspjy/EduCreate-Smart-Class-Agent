"""教师自然语言修改意见的确定性解析器。

比赛环境默认不依赖外部 LLM：常见中文指令由规则解析为白名单动作，
无法确定时返回 warning，交由教师确认或稍后使用 LLM 增强。
"""

import re

from app.schemas.pptagent import PptEditAction


def _section_index(instruction: str, sections: list[dict]) -> int | None:
    match = re.search(r"第\s*(\d+)\s*(?:个)?\s*(?:章节|小节|节|章)", instruction)
    if match:
        index = int(match.group(1)) - 1
        return index if 0 <= index < len(sections) else None
    for index, section in enumerate(sections):
        title = str(section.get("title") or "").strip()
        if title and title in instruction:
            return index
    return None


def rewrite_instruction(outline: dict, instruction: str) -> tuple[list[PptEditAction], list[str], float, str]:
    sections = outline.get("sections") if isinstance(outline, dict) else None
    if not isinstance(sections, list) or not sections:
        return [], ["当前大纲没有可编辑章节"], 0.0, "无法定位章节"
    text = " ".join(instruction.strip().split())
    index = _section_index(text, sections)
    actions: list[PptEditAction] = []
    warnings: list[str] = []

    style = None
    if any(word in text for word in ("活泼", "现代", "清新")):
        style = "modern"
    elif any(word in text for word in ("简洁", "极简", "留白")):
        style = "minimal"
    elif any(word in text for word in ("传统", "经典", "稳重")):
        style = "classic"
    if style:
        actions.append(PptEditAction(type="set_style", style=style))

    if any(word in text for word in ("上移", "前移", "提前")) or "移到最前" in text:
        if index is None:
            warnings.append("未能定位需要上移的章节，请写明“第 N 节”或章节标题")
        elif index == 0:
            warnings.append("该章节已经位于最前")
        else:
            actions.append(PptEditAction(type="move_section", section_id=str(sections[index].get("id")), to_index=index - 1))
    elif any(word in text for word in ("下移", "后移", "推后")) or "移到最后" in text:
        if index is None:
            warnings.append("未能定位需要下移的章节，请写明“第 N 节”或章节标题")
        elif index == len(sections) - 1:
            warnings.append("该章节已经位于最后")
        else:
            actions.append(PptEditAction(type="move_section", section_id=str(sections[index].get("id")), to_index=index + 1))
    else:
        target_match = re.search(r"移到\s*第\s*(\d+)\s*(?:个)?\s*(?:章节|小节|节|章)", text)
        if target_match and index is not None:
            target = min(max(int(target_match.group(1)) - 1, 0), len(sections) - 1)
            actions.append(PptEditAction(type="move_section", section_id=str(sections[index].get("id")), to_index=target))

    rename = re.search(r"(?:改名为|改成|修改为|命名为)\s*[“\"]?([^”\"]+)[”\"]?", text)
    if rename and index is not None and any(word in text for word in ("标题", "章节", "小节", "改名", "改成", "命名")) and not (style and "风格" in text):
        actions.append(PptEditAction(type="rename_section", section_id=str(sections[index].get("id")), title=rename.group(1).strip(" 。，,")))

    append = re.search(r"(?:增加|添加|补充|加入)(?:一个|一条)?(?:要点|重点|内容)?[：: ]?(.+)$", text)
    if append and index is not None:
        bullet = append.group(1).strip(" 。，,")
        bullet = re.split(r"[，,]\s*(?:并)?(?:改成|改为|设置为).*$", bullet)[0].strip(" 。，,")
        if bullet:
            actions.append(PptEditAction(type="append_bullet", section_id=str(sections[index].get("id")), text=bullet))

    bullet_index = re.search(r"第\s*(\d+)\s*(?:个)?要点", text)
    if bullet_index and index is not None:
        position = int(bullet_index.group(1)) - 1
        if any(word in text for word in ("删除", "移除")):
            actions.append(PptEditAction(type="remove_bullet", section_id=str(sections[index].get("id")), bullet_index=position))
        else:
            replacement = re.search(r"(?:改为|改成|修改为)\s*[“\"]?([^”\"]+)[”\"]?", text)
            if replacement:
                actions.append(PptEditAction(type="replace_bullet", section_id=str(sections[index].get("id")), bullet_index=position, text=replacement.group(1).strip(" 。，,")))

    if not actions:
        warnings.append("没有识别出可执行动作，请明确章节序号、要点序号或主题关键词")
    confidence = min(1.0, 0.45 + 0.15 * len(actions)) if actions else 0.0
    explanation = "已将意见改写为安全结构化动作，请确认后应用" if actions else "意见未转换为动作，未执行任何修改"
    return actions, warnings, confidence, explanation
