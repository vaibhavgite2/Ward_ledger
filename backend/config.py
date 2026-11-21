"""Central configuration. Everything overridable by environment variable."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("WL_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("WL_DB_PATH", BACKEND / "ward_ledger.db"))
CACHE_DIR = Path(os.environ.get("WL_CACHE_DIR", BACKEND / ".cache" / "claude"))
PROMPTS_DIR = BACKEND / "prompts"

# Models (SPEC §9.1)
MODEL_FAST = os.environ.get("WL_MODEL_FAST", "claude-haiku-5-5")
MODEL_WRITER = os.environ.get("WL_MODEL_WRITER", "claude-sonnet-5-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Set WL_DISABLE_CLAUDE=1 to force the deterministic fallbacks (used by tests).
CLAUDE_ENABLED = bool(ANTHROPIC_API_KEY) and os.environ.get("WL_DISABLE_CLAUDE") != "1"

# "Today" for the dataset: open issues, remaining budget, recent rain.
AS_OF = os.environ.get("WL_AS_OF", "2025-10-05")

RULES = yaml.safe_load((BACKEND / "rules" / "config.yaml").read_text(encoding="utf-8"))

SYNTHETIC_NOTICE = "Demo data: all records are synthetic and all contractors are fictional."

# CSV files that make up the source layer.
SOURCE_FILES = [
    "work_orders", "complaints", "roads", "wards", "contractors", "rate_card",
    "localities", "flood_hotspots", "rainfall_daily", "tides", "traffic",
    "accidents", "facilities", "social_posts",
]
GEOJSON_FILES = ["wards.geojson", "roads.geojson"]
