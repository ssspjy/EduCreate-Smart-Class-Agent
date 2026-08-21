"""PPTX 文件生成器（基于 python-pptx）。

文档 §3.2 services/generators/pptx_generator.py：
将 OutlineResponse 格式的大纲数据渲染为 .pptx 文件。
"""

import logging
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

logger = logging.getLogger(__name__)

# 幻灯片尺寸常量
DEFAULT_WIDTH = Inches(13.33)  # 16:9 宽屏
DEFAULT_HEIGHT = Inches(7.5)


def generate_pptx(outline: dict, output_path: str) -> str:
    """将大纲数据渲染为 PPTX 文件。

    Args:
        outline: OutlineResponse 字典，包含 title / subject / grade / sections
        output_path: 输出文件路径

    Returns:
        输出文件的绝对路径
    """
    prs = Presentation()
    prs.slide_width = DEFAULT_WIDTH
    prs.slide_height = DEFAULT_HEIGHT

    # ── 封面页 ───────────────────────────────────────────────────────────
    _add_cover(prs, outline)

    # ── 目录页 ───────────────────────────────────────────────────────────
    _add_toc(prs, outline)

    # ── 章节页 ───────────────────────────────────────────────────────────
    for section in outline.get("sections", []):
        _add_section(prs, section, outline.get("ppt_style"))

    # ── 保存 ────────────────────────────────────────────────────────────
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output))
    logger.info("[PPTX] 生成成功：%s，%d 张幻灯片", output, len(prs.slides))
    return str(output)


# ── 内部函数 ──────────────────────────────────────────────────────────────────

def _add_cover(prs: Presentation, outline: dict) -> None:
    """封面幻灯片。"""
    slide_layout = prs.slide_layouts[6]  # 空白布局
    slide = prs.slides.add_slide(slide_layout)

    # 标题
    colors = _style_colors(outline.get("ppt_style"))
    _add_textbox(
        slide,
        outline.get("title", "未命名课件"),
        left=Inches(0.5), top=Inches(2.5),
        width=Inches(12.33), height=Inches(1.5),
        font_size=Pt(44), bold=True, color=colors[0],
    )
    # 副标题
    _add_textbox(
        slide,
        f"科目：{outline.get('subject', '')}  ·  年级：{outline.get('grade', '')}",
        left=Inches(0.5), top=Inches(4.2),
        width=Inches(12.33), height=Inches(0.6),
        font_size=Pt(20), color=colors[1],
    )
    # 总页数
    _add_textbox(
        slide,
        f"共 {_expected_slide_count(outline)} 页 · {_expected_duration(outline)} 分钟",
        left=Inches(0.5), top=Inches(5.0),
        width=Inches(12.33), height=Inches(0.5),
        font_size=Pt(14), color=colors[2],
    )


def _add_toc(prs: Presentation, outline: dict) -> None:
    """目录幻灯片。"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    colors = _style_colors(outline.get("ppt_style"))
    _add_textbox(
        slide, "📋 目录",
        left=Inches(0.5), top=Inches(0.5),
        width=Inches(12.33), height=Inches(0.8),
        font_size=Pt(32), bold=True, color=colors[0],
    )

    sections = outline.get("sections", [])
    y = Inches(1.6)
    for i, section in enumerate(sections):
        _add_textbox(
            slide,
            f"{i + 1}. {section.get('title', '')}",
            left=Inches(1.0), top=y,
            width=Inches(10), height=Inches(0.6),
            font_size=Pt(18), color=colors[1],
        )
        y += Inches(0.65)


def _add_section(prs: Presentation, section: dict, style: str | None = None) -> None:
    """Render exactly the requested number of slides for one section."""
    slide_layout = prs.slide_layouts[6]
    title = section.get("title", "未命名章节")
    bullets = [str(item).strip() for item in section.get("bullets", []) if str(item).strip()]
    duration = _bounded_int(section.get("duration_minutes", 0), minimum=0)
    slide_count = _bounded_int(section.get("slide_count", 1), minimum=1)
    colors = _style_colors(style)

    if slide_count == 1:
        _add_section_content_slide(
            prs,
            slide_layout,
            title,
            bullets,
            duration,
            colors,
            compact_title=True,
        )
        return

    # 多页章节使用一张标题页，其余页平均承载要点。
    title_slide = prs.slides.add_slide(slide_layout)
    _add_textbox(
        title_slide, title,
        left=Inches(0.5), top=Inches(2.8),
        width=Inches(12.33), height=Inches(1.2),
        font_size=Pt(40), bold=True, color=colors[0],
    )
    _add_textbox(
        title_slide, f"{duration} 分钟 · {slide_count} 页",
        left=Inches(0.5), top=Inches(4.2),
        width=Inches(12.33), height=Inches(0.5),
        font_size=Pt(16), color=colors[1],
    )

    content_count = slide_count - 1
    for page_index in range(content_count):
        start = len(bullets) * page_index // content_count
        end = len(bullets) * (page_index + 1) // content_count
        _add_section_content_slide(
            prs,
            slide_layout,
            title,
            bullets[start:end],
            duration,
            colors,
            page_index=page_index + 1,
            content_count=content_count,
        )


def _add_section_content_slide(
    prs: Presentation,
    slide_layout,
    title: str,
    bullets: list[str],
    duration: int,
    colors: tuple[str, str, str],
    *,
    compact_title: bool = False,
    page_index: int = 1,
    content_count: int = 1,
) -> None:
    """Add one content slide while keeping text within the fixed canvas."""
    slide = prs.slides.add_slide(slide_layout)
    title_text = title if content_count == 1 else f"{title}（{page_index}/{content_count}）"
    _add_textbox(
        slide,
        title_text,
        left=Inches(0.5), top=Inches(0.35 if not compact_title else 0.6),
        width=Inches(12.33), height=Inches(0.85),
        font_size=Pt(28 if not compact_title else 32), bold=True, color=colors[0],
    )
    if compact_title:
        _add_textbox(
            slide,
            f"{duration} 分钟",
            left=Inches(0.5), top=Inches(1.35),
            width=Inches(12.33), height=Inches(0.4),
            font_size=Pt(15), color=colors[1],
        )

    y = Inches(1.8 if compact_title else 1.3)
    for bullet in bullets[:8]:
        _add_textbox(
            slide,
            f"• {bullet}",
            left=Inches(0.8), top=y,
            width=Inches(11.5), height=Inches(0.6),
            font_size=Pt(18), color=colors[1],
        )
        y += Inches(0.65)


def _bounded_int(value: object, *, minimum: int) -> int:
    try:
        return max(int(value or 0), minimum)
    except (TypeError, ValueError):
        return minimum


def _expected_slide_count(outline: dict) -> int:
    sections = outline.get("sections", []) if isinstance(outline, dict) else []
    return 2 + sum(_bounded_int(section.get("slide_count", 1), minimum=1) for section in sections if isinstance(section, dict))


def _expected_duration(outline: dict) -> int:
    sections = outline.get("sections", []) if isinstance(outline, dict) else []
    return sum(_bounded_int(section.get("duration_minutes", 0), minimum=0) for section in sections if isinstance(section, dict))


def _style_colors(style: str | None) -> tuple[str, str, str]:
    """固定的安全主题令牌，避免把任意颜色/代码交给生成器。"""
    return {
        "modern": ("0F766E", "115E59", "5EEAD4"),
        "minimal": ("111827", "374151", "9CA3AF"),
        "classic": ("1F2937", "374151", "9CA3AF"),
    }.get(style or "classic", ("1F2937", "374151", "9CA3AF"))


def _add_textbox(
    slide,
    text: str,
    left, top, width, height,
    font_size=Pt(14),
    bold=False,
    color="000000",
) -> None:
    """向幻灯片添加文本框。"""
    from pptx.dml.color import RGBColor

    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = font_size
    p.font.bold = bold
    p.font.color.rgb = RGBColor.from_string(color)
