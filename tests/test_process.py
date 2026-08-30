"""Unit tests for the pure parts of the process stage (no API)."""

import pytest

from pipeline.config import CACHE_DIR
from pipeline.process import build_system_prompt, upload_path
from pipeline.registry import get_schema


def test_upload_path_reduces_traversal_to_basename():
    uploads_dir = CACHE_DIR / "uploads"
    assert upload_path("../../etc/passwd") == uploads_dir / "passwd"
    assert upload_path("/absolute/evil.txt") == uploads_dir / "evil.txt"
    assert upload_path("letter.pdf") == uploads_dir / "letter.pdf"


def test_upload_path_rejects_empty_names():
    for bad in ("", ".", "..", "/"):
        with pytest.raises(ValueError):
            upload_path(bad)


def test_tool_schema_requires_every_field():
    schema = get_schema("haematology_2ww")
    assert set(schema.json_schema["required"]) == set(schema.json_schema["properties"])
    assert "document_type" in schema.json_schema["required"]


def test_prompt_asks_for_crop_detection():
    assert "cropped" in build_system_prompt(get_schema())
