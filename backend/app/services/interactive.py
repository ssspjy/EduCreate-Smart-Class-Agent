"""基于固定 Jinja2 模板生成课堂互动内容。"""

from jinja2 import Environment, StrictUndefined, select_autoescape

from app.schemas.interactive import InteractiveGenerateRequest, InteractiveItem


_HTML_TEMPLATE = """<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>{{ title }}</title>
<style>body{font-family:Arial,'Microsoft YaHei',sans-serif;padding:24px;color:#1f2937}h1{font-size:24px}article{border:1px solid #dbe3ef;border-radius:10px;padding:16px;margin:12px 0}li{margin:6px 0}details{margin-top:12px;color:#2563eb}</style>
</head><body><h1>{{ title }}</h1>
{% for item in items %}<article><strong>{{ loop.index }}. {{ item.prompt }}</strong>
{% if item.options %}<ol type=\"A\">{% for option in item.options %}<li>{{ option }}</li>{% endfor %}</ol>{% endif %}
<details><summary>查看参考答案</summary><p>{{ item.answer }}</p><p>{{ item.explanation }}</p></details></article>{% endfor %}
</body></html>"""

_env = Environment(undefined=StrictUndefined, autoescape=select_autoescape(["html", "xml"]))
_template = _env.from_string(_HTML_TEMPLATE)


def _source_sections(outline: dict, section_id: str | None) -> list[dict]:
    sections = outline.get("sections") if isinstance(outline, dict) else None
    if not isinstance(sections, list):
        return []
    if section_id:
        return [section for section in sections if section.get("id") == section_id]
    return sections


def generate_interactive(request: InteractiveGenerateRequest) -> tuple[list[InteractiveItem], str, list[str]]:
    sections = _source_sections(request.outline, request.section_id)
    bullets = [
        str(bullet).strip()
        for section in sections
        for bullet in section.get("bullets", [])
        if str(bullet).strip()
    ]
    warnings: list[str] = []
    if not sections:
        warnings.append("未找到指定章节，未生成互动内容")
    if not bullets:
        warnings.append("当前大纲没有可用要点，请先补充章节内容")
    items: list[InteractiveItem] = []
    for index, bullet in enumerate(bullets[: request.count], start=1):
        item_id = f"q{index}"
        if request.interaction_type == "choice":
            distractors = [candidate for candidate in bullets if candidate != bullet][:2]
            options = [bullet, *distractors]
            while len(options) < 3:
                options.append(f"与{bullet}无关的说法")
            items.append(InteractiveItem(id=item_id, type="choice", prompt="下列哪一项最符合本节要点？", options=options, answer="A", explanation=f"依据大纲要点：{bullet}"))
        elif request.interaction_type == "true_false":
            items.append(InteractiveItem(id=item_id, type="true_false", prompt=bullet, answer="正确", explanation="该判断直接来自当前章节要点。"))
        else:
            items.append(InteractiveItem(id=item_id, type="fill_blank", prompt=f"请补充本节要点：____", answer=bullet, explanation="答案取自当前章节的结构化要点。"))
    if len(items) < request.count and bullets:
        warnings.append(f"可用要点只有 {len(bullets)} 条，实际生成 {len(items)} 题")
    title = str(request.outline.get("title") or "课堂互动练习")
    html = _template.render(title=title, items=[item.model_dump() for item in items])
    return items, html, warnings
