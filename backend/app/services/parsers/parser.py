"""Material parser entrypoint with explicit partial-capability warnings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
    warnings = []
    if empty_pages:
        warnings.append(
            f"{len(empty_pages)} 个 PDF 页面没有可提取文本，可能需要 OCR"
        )
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
        chunks, warnings = _parse_pdf(path)
        return ParseResult(chunks=chunks, warnings=warnings)
    if extension == "docx":
        return ParseResult(chunks=_parse_docx(path), warnings=[])
    if extension == "pptx":
        return ParseResult(chunks=_parse_pptx(path), warnings=[])
    if extension in {"md", "txt"}:
        return ParseResult(chunks=_parse_plain_text(path), warnings=[])

    if extension in {"png", "jpg", "jpeg"}:
        return ParseResult(chunks=[], warnings=["image OCR is not connected yet"])
    if extension == "mp4":
        return ParseResult(chunks=[], warnings=["video transcription is not connected yet"])
    if extension in {"doc", "ppt"}:
        return ParseResult(chunks=[], warnings=["legacy Office formats require conversion before parsing"])

    return ParseResult(chunks=[], warnings=[f"unsupported parser extension: {extension}"])
