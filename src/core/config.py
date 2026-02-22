"""Stage 0 configuration — loads .env and exposes typed settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (three levels up from src/core/config.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _require(key: str) -> str:
    """Return env var or raise with a clear message."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


# Google Sheets
GOOGLE_SHEET_ID: str = _require("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB_INPUT: str = os.getenv("GOOGLE_SHEET_TAB_INPUT", "").strip()
GOOGLE_SHEET_TAB_STATUS: str = os.getenv("GOOGLE_SHEET_TAB_STATUS", "").strip()

if not GOOGLE_SHEET_TAB_INPUT:
    raise RuntimeError("Missing required env variable: GOOGLE_SHEET_TAB_INPUT")

if not GOOGLE_SHEET_TAB_STATUS:
    raise RuntimeError("Missing required env variable: GOOGLE_SHEET_TAB_STATUS")

GOOGLE_SHEET_TAB: str = GOOGLE_SHEET_TAB_INPUT  # alias used by run_once

GOOGLE_SERVICE_ACCOUNT_JSON: str = _require("GOOGLE_SERVICE_ACCOUNT_JSON")

# SMTP
SMTP_HOST: str = _require("SMTP_HOST")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = _require("SMTP_USER")
SMTP_PASS: str = _require("SMTP_PASS")
SMTP_FROM_EMAIL: str = _require("SMTP_FROM_EMAIL")
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "").strip()

# Calendar
CALENDAR_URL: str = _require("CALENDAR_URL")

# Attachments (paths relative to project root)
STAGE0_PDF_1: str = _require("STAGE0_PDF_1")
STAGE0_PDF_2: str = _require("STAGE0_PDF_2")
STAGE0_PDF_3: str = _require("STAGE0_PDF_3")

# Aliases used by run_once (map old names → new STAGE0_PDF_* constants)
ATTACHMENT_A: str = STAGE0_PDF_1
ATTACHMENT_B: str = STAGE0_PDF_2
ATTACHMENT_C: str = STAGE0_PDF_3

APP_ENV: str = os.getenv("APP_ENV", "local").strip()

# Test mode — redirects all outbound emails to a single internal address.
# TEST_RECIPIENT_EMAIL is validated at runtime (process_new_leads startup),
# not here, because it is only required when STAGE0_TEST_MODE=1.
STAGE0_TEST_MODE: bool = os.getenv("STAGE0_TEST_MODE", "0").strip() == "1"
TEST_RECIPIENT_EMAIL: str | None = os.getenv("TEST_RECIPIENT_EMAIL", "").strip() or None
