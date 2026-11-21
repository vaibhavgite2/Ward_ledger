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

# Live operations (accounts, complaint tickets, tasks, uploads). Never touched by the analytics pipeline.
INSTANCE_DIR = Path(os.environ.get("WL_INSTANCE_DIR", BACKEND / "instance"))
UPLOAD_DIR = Path(os.environ.get("WL_UPLOAD_DIR", INSTANCE_DIR / "uploads"))
SESSION_HOURS = {"citizen": 24 * 14, "officer": 12, "contractor": 24 * 3}

# E-mail (complaint resolved -> citizen, overdue task -> contractor). With no WL_SMTP_HOST nothing leaves the machine:
# messages are written to the `email_outbox` table with status 'logged' so the flow can be demonstrated and audited.
SMTP_HOST = os.environ.get("WL_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("WL_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("WL_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("WL_SMTP_PASSWORD", "")
SMTP_SECURITY = os.environ.get("WL_SMTP_SECURITY", "starttls")      # starttls | ssl | none
MAIL_FROM = os.environ.get("WL_MAIL_FROM", "The Ward Ledger <no-reply@wardledger.example>")
APP_URL = os.environ.get("WL_APP_URL", "http://localhost:3000").rstrip("/")   # base of the links inside e-mails
# How often the API checks for tasks that missed their deadline (minutes; 0 turns the background check off).
OVERDUE_CHECK_MINUTES = float(os.environ.get("WL_OVERDUE_CHECK_MIN", "15"))

# CSV files that make up the source layer.
SOURCE_FILES = [
    "work_orders", "complaints", "roads", "wards", "contractors", "rate_card",
    "localities", "flood_hotspots", "rainfall_daily", "tides", "traffic",
    "accidents", "facilities", "social_posts",
]
GEOJSON_FILES = ["wards.geojson", "roads.geojson"]
