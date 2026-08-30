"""Schema registry: extraction schemas defined as config files, not code.

Each JSON file in schemas/ fully describes one document type: its fields
(types, descriptions, format patterns, critical flags) and UI grouping.
The pydantic model, LLM tool schema, prompt rules and validators are all
generated from it — adding a new specialty is a config file, not code.

Two triage fields (document_type, additional_findings) are injected into
every schema automatically.
"""

import json
from functools import lru_cache

from pydantic import BaseModel, Field, create_model

from pipeline.config import PROJECT_ROOT

SCHEMA_DIR = PROJECT_ROOT / "schemas"
DEFAULT_SCHEMA = "haematology_2ww"
FALLBACK_SCHEMA = "generic_referral"

_ADDITIONAL_FINDINGS_DESCRIPTION = (
    "Anything clinically or administratively significant in the letter that does "
    "not fit any other field — e.g. safeguarding concerns, allergy warnings, DNR "
    "status, a second patient mentioned. Empty string if none."
)


def _field_definition(name: str, spec: dict) -> tuple:
    kind = spec["type"]
    description = spec.get("description", "")
    if kind == "str":
        return (str, Field("", description=description))
    if kind == "bool":
        return (bool, Field(False, description=description))
    if kind == "list[str]":
        return (list[str], Field(default_factory=list, description=description))
    if kind == "object":
        nested = create_model(
            name.capitalize(),
            **{sub: _field_definition(sub, s) for sub, s in spec["fields"].items()},
        )
        return (nested, Field(default_factory=nested, description=description))
    raise ValueError(f"Unknown field type '{kind}' for field '{name}'")


class Schema:
    """One document type: generated model + everything derived from its config."""

    def __init__(self, cfg: dict):
        self.name: str = cfg["name"]
        self.display_name: str = cfg["display_name"]
        self.document_description: str = cfg["document_description"]
        self.domain_prompt: str = cfg.get("domain_prompt", "")
        self.groups: dict[str, list[str]] = {
            **cfg["groups"],
            "Triage": ["document_type", "additional_findings"],
        }
        self.format_rules: dict[str, tuple[str, str]] = {
            f: (s["pattern"], s["hint"])
            for f, s in cfg["fields"].items()
            if "pattern" in s
        }
        self.critical_fields: list[str] = [
            f for f, s in cfg["fields"].items() if s.get("critical")
        ]

        fields = {
            "document_type": {
                "type": "str",
                "description": (
                    f"'referral' if this document is {self.document_description}. "
                    "Otherwise a short description of what the document actually is, "
                    "e.g. 'discharge summary', 'not a medical document'."
                ),
            },
            "additional_findings": {
                "type": "str",
                "description": _ADDITIONAL_FINDINGS_DESCRIPTION,
            },
            **cfg["fields"],
        }
        self.model: type[BaseModel] = create_model(
            _pascal_case(self.name),
            **{f: _field_definition(f, s) for f, s in fields.items()},
        )
        self.json_schema: dict = self.model.model_json_schema()


def _pascal_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


@lru_cache
def get_schema(name: str = DEFAULT_SCHEMA) -> Schema:
    path = SCHEMA_DIR / f"{name}.json"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in SCHEMA_DIR.glob("*.json")))
        raise ValueError(f"Unknown schema '{name}'. Available: {available}")
    return Schema(json.loads(path.read_text()))


def list_schemas() -> list[str]:
    return sorted(p.stem for p in SCHEMA_DIR.glob("*.json"))
