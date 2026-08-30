"""Unit tests for the ingest stage, using real files from the (local-only) dataset."""

import base64

import pytest

from pipeline.config import REFERRAL_DIR
from pipeline.ingest import SUPPORTED_EXTENSIONS, ingest

pytestmark = pytest.mark.skipif(
    not REFERRAL_DIR.exists(), reason="local data/ folder not present"
)


def _one_file_with_suffix(suffix):
    return next(p for p in sorted(REFERRAL_DIR.iterdir()) if p.suffix == suffix)


def test_every_dataset_file_is_supported():
    files = [p for p in REFERRAL_DIR.iterdir() if not p.name.startswith(".")]
    assert files, "dataset is empty"
    assert all(p.suffix.lower() in SUPPORTED_EXTENSIONS for p in files)


def test_txt_becomes_text_block():
    blocks = ingest(_one_file_with_suffix(".txt"))
    assert blocks[0]["type"] == "text"
    assert len(blocks[0]["text"]) > 100


def test_docx_text_is_extracted():
    blocks = ingest(_one_file_with_suffix(".docx"))
    assert blocks[0]["type"] == "text"
    assert "NHS" in blocks[0]["text"] or "referral" in blocks[0]["text"].lower()


def test_pdf_becomes_document_block():
    blocks = ingest(_one_file_with_suffix(".pdf"))
    assert blocks[0]["type"] == "document"
    assert blocks[0]["source"]["media_type"] == "application/pdf"


def test_heic_is_converted_to_jpeg():
    blocks = ingest(_one_file_with_suffix(".heic"))
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/jpeg"
    jpeg_bytes = base64.b64decode(blocks[0]["source"]["data"])
    assert jpeg_bytes[:2] == b"\xff\xd8"  # JPEG magic number


def test_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "letter.xyz"
    bad.write_text("hello")
    with pytest.raises(ValueError):
        ingest(bad)


def test_oversized_image_is_recompressed_under_api_limit():
    from pipeline.ingest import MAX_RAW_IMAGE_BYTES
    big = REFERRAL_DIR / "referral-hzq.png"  # 10.8MB as base64, over the 10MB cap
    if big.stat().st_size * 4 / 3 < 10_485_760:
        pytest.skip("dataset file no longer oversized")
    blocks = ingest(big)
    raw = len(base64.b64decode(blocks[0]["source"]["data"]))
    assert raw <= MAX_RAW_IMAGE_BYTES
    assert blocks[0]["source"]["media_type"] == "image/jpeg"
