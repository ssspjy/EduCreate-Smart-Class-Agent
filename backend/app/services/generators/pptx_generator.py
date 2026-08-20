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
        _add_section(prs, section)

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
    _add_textbox(
        slide,
        outline.get("title", "未命名课件"),
        left=Inches(0.5), top=Inches(2.5),
        width=Inches(12.33), height=Inches(1.5),
        font_size=Pt(44), bold=True, color="1F2937",
    )
    # 副标题
    _add_textbox(
        slide,
        f"科目：{outline.get('subject', '')}  ·  年级：{outline.get('grade', '')}",
        left=Inches(0.5), top=Inches(4.2),
        width=Inches(12.33), height=Inches(0.6),
        font_size=Pt(20), color="6B7280",
    )
    # 总页数
    _add_textbox(
        slide,
        f"共 {outline.get('total_slides', 0)} 页 · {outline.get('total_duration_minutes', 0)} 分钟",
        left=Inches(0.5), top=Inches(5.0),
        width=Inches(12.33), height=Inches(0.5),
        font_size=Pt(14), color="9CA3AF",
    )


def _add_toc(prs: Presentation, outline: dict) -> None:
    """目录幻灯片。"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    _add_textbox(
        slide, "📋 目录",
        left=Inches(0.5), top=Inches(0.5),
        width=Inches(12.33), height=Inches(0.8),
        font_size=Pt(32), bold=True, color="1F2937",
    )

    sections = outline.get("sections", [])
    y = Inches(1.6)
    for i, section in enumerate(sections):
        _add_textbox(
            slide,
            f"{i + 1}. {section.get('title', '')}",
            left=Inches(1.0), top=y,
            width=Inches(10), height=Inches(0.6),
            font_size=Pt(18), color="374151",
        )
        y += Inches(0.65)


def _add_section(prs: Presentation, section: dict) -> None:
    """单个章节幻灯片（标题页 + 内容页）。"""
    slide_layout = prs.slide_layouts[6]
    title = section.get("title", "未命名章节")
    bullets = section.get("bullets", [])
    duration = section.get("duration_minutes", 0)
    slide_count = section.get("slide_count", 1)

    # 标题页
    slide = prs.slides.add_slide(slide_layout)
    _add_textbox(
        slide, title,
        left=Inches(0.5), top=Inches(2.8),
        width=Inches(12.33), height=Inches(1.2),
        font_size=Pt(40), bold=True, color="1F2937",
    )
    _add_textbox(
        slide, f"{duration} 分钟 · {slide_count} 页",
        left=Inches(0.5), top=Inches(4.2),
        width=Inches(12.33), height=Inches(0.5),
        font_size=Pt(16), color="6B7280",
    )

    # 内容页
    if bullets:
        content_slide = prs.slides.add_slide(slide_layout)
        _add_textbox(
            content_slide, title,
            left=Inches(0.5), top=Inches(0.3),
            width=Inches(12.33), height=Inches(0.8),
            font_size=Pt(28), bold=True, color="1F2937",
        )

        y = Inches(1.3)
        for bullet in bullets:
            _add_textbox(
                content_slide,
                f"• {bullet}",
                left=Inches(0.8), top=y,
                width=Inches(11.5), height=Inches(0.6),
                font_size=Pt(18), color="374151",
            )
            y += Inches(0.65)
            if y > Inches(6.5):
                break  # 防止超出页面


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
