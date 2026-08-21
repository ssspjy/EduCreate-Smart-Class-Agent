"""Bounded OCR helpers backed by PDFium, Pillow and Tesseract."""

from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path
from threading import BoundedSemaphore


_OCR_SLOTS = BoundedSemaphore(value=2)


@dataclass
class OCRResult:
    """Text recognized per source page plus non-fatal runtime warnings."""

    text_by_page: dict[int, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _recognize_image(
    image: object,
    language: str,
    timeout_seconds: int,
    max_pixels: int,
) -> str:
    import pytesseract
    from PIL import ImageOps

    prepared = ImageOps.autocontrast(ImageOps.grayscale(image))
    if prepared.width * prepared.height > max_pixels:
        ratio = sqrt(max_pixels / (prepared.width * prepared.height))
        prepared = prepared.resize(
            (max(1, int(prepared.width * ratio)), max(1, int(prepared.height * ratio)))
        )
    with _OCR_SLOTS:
        return pytesseract.image_to_string(
            prepared,
            lang=language,
            config="--psm 6",
            timeout=timeout_seconds,
        ).strip()


def _warning_for_exception(exc: Exception) -> str:
    """Return a stable user-facing warning without leaking local paths."""
    name = type(exc).__name__
    if name == "TesseractNotFoundError":
        return "OCR 运行时不可用，请安装 Tesseract 或使用 Docker 版本"
    if name == "RuntimeError" and "timeout" in str(exc).lower():
        return "OCR 处理超时，已保留其他可提取内容"
    return f"OCR 处理失败（{name}），已保留其他可提取内容"


def ocr_image(
    path: Path,
    language: str,
    timeout_seconds: int,
    max_pixels: int,
) -> OCRResult:
    """Recognize a standalone image without making OCR failure fatal."""
    from PIL import Image, ImageOps

    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            text = _recognize_image(image, language, timeout_seconds, max_pixels)
        if text:
            return OCRResult(text_by_page={1: text})
        return OCRResult(warnings=["图片 OCR 未识别到文本"])
    except Exception as exc:
        return OCRResult(warnings=[_warning_for_exception(exc)])


def ocr_pdf_pages(
    path: Path,
    page_numbers: list[int],
    language: str,
    dpi: int,
    timeout_seconds: int,
    max_pixels: int,
) -> OCRResult:
    """Render selected 1-based PDF pages and recognize them with Tesseract."""
    import pypdfium2 as pdfium

    result = OCRResult()
    try:
        document = pdfium.PdfDocument(str(path))
    except Exception as exc:
        result.warnings.append(_warning_for_exception(exc))
        return result

    try:
        requested_scale = dpi / 72
        for page_number in page_numbers:
            try:
                page = document.get_page(page_number - 1)
                try:
                    width, height = page.get_size()
                    pixel_limited_scale = sqrt(max_pixels / max(1, width * height))
                    scale = min(requested_scale, pixel_limited_scale)
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil()
                        text = _recognize_image(
                            image,
                            language,
                            timeout_seconds,
                            max_pixels,
                        )
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                if text:
                    result.text_by_page[page_number] = text
            except Exception as exc:
                warning = _warning_for_exception(exc)
                if warning not in result.warnings:
                    result.warnings.append(warning)
                if type(exc).__name__ == "TesseractNotFoundError":
                    break
    finally:
        document.close()

    return result
