"""PPTAgent 的确定性结构化编辑动作执行器。"""

from copy import deepcopy
from fastapi import HTTPException
from app.schemas.pptagent import PptEditAction


def apply_actions(outline: dict, actions: list[PptEditAction]) -> tuple[dict, list[dict], list[str]]:
    result = deepcopy(outline)
    sections = result.get("sections")
    if not isinstance(sections, list):
        raise HTTPException(status_code=422, detail="outline.sections 必须是数组")
    applied: list[dict] = []
    warnings: list[str] = []
    for action in actions:
        data = action.model_dump(exclude_none=True)
        if action.type == "move_section" and action.to_index is None:
            raise HTTPException(status_code=422, detail="move_section 必须提供 to_index")
        if action.type == "rename_section" and not (action.title or "").strip():
            raise HTTPException(status_code=422, detail="rename_section 必须提供非空 title")
        if action.type in {"replace_bullet", "append_bullet"} and not (action.text or "").strip():
            raise HTTPException(status_code=422, detail=f"{action.type} 必须提供非空 text")
        if action.type in {"replace_bullet", "remove_bullet"} and action.bullet_index is None:
            raise HTTPException(status_code=422, detail=f"{action.type} 必须提供 bullet_index")
        if action.type == "set_style" and action.style is None:
            raise HTTPException(status_code=422, detail="set_style 必须提供 style")
        section = next((item for item in sections if item.get("id") == action.section_id), None) if action.section_id else None
        if action.type in {"move_section", "rename_section", "replace_bullet", "append_bullet", "remove_bullet"} and section is None:
            warnings.append(f"未找到章节：{action.section_id or '未提供'}")
            continue
        if action.type == "move_section":
            old = sections.index(section)
            target = min(action.to_index or 0, len(sections) - 1)
            sections.insert(target, sections.pop(old))
        elif action.type == "rename_section":
            section["title"] = (action.title or "").strip()
        elif action.type == "append_bullet":
            section.setdefault("bullets", []).append((action.text or "").strip())
        elif action.type == "replace_bullet":
            bullets = section.setdefault("bullets", [])
            if action.bullet_index is None or action.bullet_index >= len(bullets):
                warnings.append(f"章节 {action.section_id} 的要点索引越界")
                continue
            bullets[action.bullet_index] = (action.text or "").strip()
        elif action.type == "remove_bullet":
            bullets = section.setdefault("bullets", [])
            if action.bullet_index is None or action.bullet_index >= len(bullets):
                warnings.append(f"章节 {action.section_id} 的要点索引越界")
                continue
            bullets.pop(action.bullet_index)
        elif action.type == "set_style":
            result["ppt_style"] = action.style
        applied.append(data)
    result["total_slides"] = 2 + sum(max(int(item.get("slide_count", 1)), 1) for item in sections)
    result["total_duration_minutes"] = sum(max(int(item.get("duration_minutes", 0)), 0) for item in sections)
    return result, applied, warnings


def build_edit_actions(outline: dict) -> list[dict]:
    return []
