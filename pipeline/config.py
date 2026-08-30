"""Central config: paths and API keys (BYOK via env.local)."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REFERRAL_DIR = DATA_DIR / "referral-files"
GROUND_TRUTH_PATH = DATA_DIR / "output-true-values.json"
CACHE_DIR = PROJECT_ROOT / ".cache"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

load_dotenv(PROJECT_ROOT / "env.local")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CLAUDE_MODEL = "claude-sonnet-5"
OPENAI_MODEL = "gpt-4o"


def require_anthropic_key() -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to env.local in the project root."
        )
    return ANTHROPIC_API_KEY
