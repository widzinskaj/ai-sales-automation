"""Stage 0 configuration — loads .env and exposes typed settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from core/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _require(key: str) -> str:
    """Return env var or raise with a clear message."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


# Google Sheets
GOOGLE_SHEET_ID: str = _require("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB: str = os.getenv("GOOGLE_SHEET_TAB", "leads").strip()
GOOGLE_SERVICE_ACCOUNT_JSON: str = _require("GOOGLE_SERVICE_ACCOUNT_JSON")

# SMTP
SMTP_HOST: str = _require("SMTP_HOST")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = _require("SMTP_USER")
SMTP_PASS: str = _require("SMTP_PASS")
SMTP_FROM_EMAIL: str = _require("SMTP_FROM_EMAIL")
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "").strip()

# Calendar
CALENDAR_LINK: str = _require("CALENDAR_LINK")

# Attachments (paths relative to project root)
ATTACHMENT_A: str = _require("ATTACHMENT_A")
ATTACHMENT_B: str = _require("ATTACHMENT_B")
ATTACHMENT_C: str = _require("ATTACHMENT_C")

APP_ENV: str = os.getenv("APP_ENV", "local").strip()
