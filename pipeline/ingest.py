"""Ingest stage: referral file -> Claude-ready content blocks.

txt  -> text block (read directly)
docx -> text block (paragraphs + tables via python-docx)
pdf  -> document block (Claude reads PDFs natively)
png/jpg -> image block
heic -> converted to jpeg in memory (Claude does not accept heic), then image block
"""

import base64
import io
from pathlib import Path

import pillow_heif
from docx import Document
from PIL import Image

pillow_heif.register_heif_opener()

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".heic"}

_IMAGE_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _base64_block(block_type: str, media_type: str, data: bytes) -> dict:
    return {
        "type": block_type,
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(data).decode(),
        },
    }


def _docx_text(path: Path) -> str:
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _heic_to_jpeg(path: Path) -> bytes:
    image = Image.open(path).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def ingest(path: Path) -> list[dict]:
    """Return the Claude message content blocks for one referral file."""
    ext = path.suffix.lower()
    if ext == ".txt":
        return [_text_block(path.read_text())]
    if ext == ".docx":
        return [_text_block(_docx_text(path))]
    if ext == ".pdf":
        return [_base64_block("document", "application/pdf", path.read_bytes())]
    if ext in _IMAGE_MEDIA_TYPES:
        return [_base64_block("image", _IMAGE_MEDIA_TYPES[ext], path.read_bytes())]
    if ext == ".heic":
        return [_base64_block("image", "image/jpeg", _heic_to_jpeg(path))]
    raise ValueError(f"Unsupported file type: {path.name}")
