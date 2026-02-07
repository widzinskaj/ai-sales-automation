"""Pure helper functions for lead processing logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def is_new_lead(row: dict[str, str]) -> bool:
    """A lead is new when it has an email but no auto_email_sent_at yet."""
    return bool(row.get("email", "").strip()) and not row.get("auto_email_sent_at", "").strip()


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 string (no microseconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def followup_due_iso(sent_at_iso: str, days: int = 3) -> str:
    """Compute followup_due_at as *sent_at + days* in ISO 8601."""
    sent = datetime.fromisoformat(sent_at_iso)
    due = sent + timedelta(days=days)
    return due.replace(microsecond=0).isoformat()


def is_followup_due(row: dict[str, str]) -> bool:
    """True when followup_due_at has passed and followup_required is not TRUE."""
    due_str = row.get("followup_due_at", "").strip()
    if not due_str:
        return False
    if row.get("followup_required", "").strip().upper() == "TRUE":
        return False
    try:
        due = datetime.fromisoformat(due_str)
    except ValueError:
        return False
    # Treat naive datetimes as UTC
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= due
