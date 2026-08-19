"""多模态解析器统一入口（占位）。

文档 §3.2 services/parsers/：PyMuPDF / python-pptx / python-docx / PaddleOCR / FFmpeg / faster-whisper。
"""


async def parse(file_path: str, file_type: str) -> dict:
    """占位：按文件类型分发到对应解析器。"""
    return {"text": "", "images": [], "metadata": {}}