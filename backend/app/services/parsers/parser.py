"""Material parser entrypoint.

The skeleton implements safe text extraction for PDF/DOCX/PPTX now. Image and
video files are accepted and persisted, but OCR/transcription are intentionally
left as explicit future stages instead of fabricating searchable text.
"""

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


def _parse_pdf(path: Path) -> list[ParsedChunk]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[ParsedChunk] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for part in _split_text(text):
            chunks.append(ParsedChunk(content=part, page_ref=page_index))
    return chunks


def _parse_docx(path: Path) -> list[ParsedChunk]:
    from docx import Document

    document = Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
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
        return ParseResult(chunks=_parse_pdf(path), warnings=[])
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
