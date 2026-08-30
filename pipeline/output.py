"""Output stage: final structured record + review flags, ready for the ops team."""

from pipeline.schema import ReferralRecord


def build_output(file_name: str, record: ReferralRecord, flags: dict[str, str]) -> dict:
    return {
        "file": file_name,
        "record": record.model_dump(),
        "review_flags": flags,
        "needs_review": bool(flags),
    }
