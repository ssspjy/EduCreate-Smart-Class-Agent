"""Material parser entrypoint with explicit partial-capability warnings."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.services.parsers.ocr import ocr_image, ocr_pdf_pages
from app.services.parsers.video import parse_video


@dataclass
class ParsedChunk:
    """Normalized parser output consumed by the persistence service."""

    content: str
    page_ref: Optional[int] = None
    bbox: Optional[list[float]] = None
    media_ref: Optional[str] = None
    modality: str = "text"


@dataclass
class ParseResult:
    """Parser result with warnings for unsupported partial capabilities."""

    chunks: list[ParsedChunk]
    warnings: list[str]


def _split_text(text: str, max_chars: int = 1200) -> list[str]:
    """Split extracted text into bounded chunks without cutting every paragraph."""
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        if current and current_len + len(paragraph) + 1 > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 1

    if current:
        chunks.append("\n".join(current))
    return chunks


def _parse_pdf(path: Path) -> tuple[list[ParsedChunk], list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[ParsedChunk] = []
    empty_pages: list[int] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts = _split_text(text)
        if not parts:
            empty_pages.append(page_index)
        for part in parts:
            chunks.append(ParsedChunk(content=part, page_ref=page_index))
    warnings: list[str] = []
    settings = get_settings()
    if empty_pages and settings.ocr_enabled:
        pages_to_ocr = empty_pages[: settings.ocr_max_pages]
        ocr_result = ocr_pdf_pages(
            path,
            pages_to_ocr,
            language=settings.ocr_language,
            dpi=settings.ocr_dpi,
            timeout_seconds=settings.ocr_timeout_seconds,
            max_pixels=settings.ocr_max_pixels,
        )
        warnings.extend(ocr_result.warnings)
        for page_number in pages_to_ocr:
            for part in _split_text(ocr_result.text_by_page.get(page_number, "")):
                chunks.append(
                    ParsedChunk(content=part, page_ref=page_number, modality="ocr")
                )
        unresolved_pages = [
            page_number
            for page_number in empty_pages
            if page_number not in ocr_result.text_by_page
        ]
        if unresolved_pages:
            warnings.append(f"{len(unresolved_pages)} 个 PDF 页面在 OCR 后仍无可提取文本")
        if len(empty_pages) > settings.ocr_max_pages:
            warnings.append(
                f"PDF 空文本页面超过 OCR 上限 {settings.ocr_max_pages} 页，其余页面未处理"
            )
    elif empty_pages:
        warnings.append(f"{len(empty_pages)} 个 PDF 页面没有可提取文本，OCR 已关闭")
    return chunks, warnings


def _parse_docx(path: Path) -> list[ParsedChunk]:
    from docx import Document

    document = Document(str(path))
    blocks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table_index, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(f"[表格 {table_index}]\n" + "\n".join(rows))
    for section in document.sections:
        for label, container in (("页眉", section.header), ("页脚", section.footer)):
            text = "\n".join(p.text.strip() for p in container.paragraphs if p.text.strip())
            if text:
                blocks.append(f"[{label}]\n{text}")
    text = "\n".join(blocks)
    return [ParsedChunk(content=part) for part in _split_text(text)]


def _parse_pptx(path: Path) -> list[ParsedChunk]:
    from pptx import Presentation

    presentation = Presentation(str(path))
    chunks: list[ParsedChunk] = []
    for slide_index, slide in enumerate(presentation.slides, start=1):
        texts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                texts.append(shape.text.strip())
        for part in _split_text("\n".join(texts)):
            chunks.append(ParsedChunk(content=part, page_ref=slide_index))
    return chunks


def _parse_plain_text(path: Path) -> list[ParsedChunk]:
    """Parse Markdown and plain-text materials as UTF-8 text."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return [ParsedChunk(content=part) for part in _split_text(text)]


async def parse(file_path: str, file_type: str) -> ParseResult:
    """Dispatch to the parser for a supported material extension."""
    path = Path(file_path)
    extension = file_type.lower().lstrip(".")

    if extension == "pdf":
        chunks, warnings = await asyncio.to_thread(_parse_pdf, path)
        return ParseResult(chunks=chunks, warnings=warnings)
    if extension == "docx":
        return ParseResult(chunks=await asyncio.to_thread(_parse_docx, path), warnings=[])
    if extension == "pptx":
        return ParseResult(chunks=await asyncio.to_thread(_parse_pptx, path), warnings=[])
    if extension in {"md", "txt"}:
        return ParseResult(chunks=await asyncio.to_thread(_parse_plain_text, path), warnings=[])

    if extension in {"png", "jpg", "jpeg"}:
        settings = get_settings()
        if not settings.ocr_enabled:
            return ParseResult(chunks=[], warnings=["图片 OCR 已关闭"])
        ocr_result = await asyncio.to_thread(
            ocr_image,
            path,
            settings.ocr_language,
            settings.ocr_timeout_seconds,
            settings.ocr_max_pixels,
        )
        chunks = [
            ParsedChunk(content=part, page_ref=1, modality="ocr")
            for part in _split_text(ocr_result.text_by_page.get(1, ""))
        ]
        return ParseResult(chunks=chunks, warnings=ocr_result.warnings)
    if extension == "mp4":
        settings = get_settings()
        video_result = await asyncio.to_thread(parse_video, path, settings)
        chunks = [
            ParsedChunk(
                content=f"[{segment.start:.1f}s–{segment.end:.1f}s] {segment.text}",
                media_ref=f"{path.name}#t={segment.start:.1f}-{segment.end:.1f}",
                modality="transcript",
            )
            for segment in video_result.segments
        ]
        return ParseResult(chunks=chunks, warnings=video_result.warnings)
    if extension in {"doc", "ppt"}:
        return ParseResult(chunks=[], warnings=["legacy Office formats require conversion before parsing"])

    return ParseResult(chunks=[], warnings=[f"unsupported parser extension: {extension}"])
