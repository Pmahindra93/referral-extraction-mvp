"""Output stage: final structured record + review flags, ready for the ops team."""

from pydantic import BaseModel

from pipeline.registry import Schema


def build_output(
    file_name: str, record: BaseModel, flags: dict[str, str], schema: Schema
) -> dict:
    return {
        "file": file_name,
        "schema": schema.name,
        "record": record.model_dump(),
        "review_flags": flags,
        "needs_review": bool(flags),
    }
