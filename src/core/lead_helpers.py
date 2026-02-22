"""Pure helper functions for lead processing logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")

# Human-friendly format for Google Sheets (no seconds, no timezone suffix).
_SHEET_DT_FMT = "%Y-%m-%d %H:%M"


def generate_vocative(full_name_or_company: str) -> str:  # noqa: ARG001
    """Return the standard Polish greeting.

    Personalisation has been removed; the greeting is always the same
    fallback so that no morphological library is required at runtime.
    """
    return "Dzień dobry,"


# ---------------------------------------------------------------------------
# Lead-state helpers
# ---------------------------------------------------------------------------

def is_new_lead(row: dict[str, str]) -> bool:
    """A lead is new when it has an email but no auto_email_sent_at yet."""
    return bool(row.get("email", "").strip()) and not row.get("auto_email_sent_at", "").strip()


def warsaw_now_formatted() -> str:
    """Current time in Europe/Warsaw as 'YYYY-MM-DD HH:MM'."""
    return datetime.now(WARSAW_TZ).strftime(_SHEET_DT_FMT)


def followup_due_formatted(sent_at_str: str, days: int = 3) -> str:
    """Compute followup_due_at as *sent_at + days*, returned in the same format."""
    sent = datetime.strptime(sent_at_str, _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    due = sent + timedelta(days=days)
    return due.strftime(_SHEET_DT_FMT)


def is_followup_due(row: dict[str, str]) -> bool:
    """True when followup_due_at has passed and followup_required is not YES."""
    due_str = row.get("followup_due_at", "").strip()
    if not due_str:
        return False
    if row.get("followup_required", "").strip().upper() == "YES":
        return False
    try:
        due = datetime.strptime(due_str, _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return False
    return datetime.now(WARSAW_TZ) >= due
