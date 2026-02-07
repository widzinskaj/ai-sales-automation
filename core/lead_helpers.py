"""Pure helper functions for lead processing logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import morfeusz2

WARSAW_TZ = ZoneInfo("Europe/Warsaw")

# Human-friendly format for Google Sheets (no seconds, no timezone suffix).
_SHEET_DT_FMT = "%Y-%m-%d %H:%M"

# Morfeusz instance — generate-only, reused across calls.
_morf = morfeusz2.Morfeusz(generate=True, analyse=False)


def to_vocative_first_name(first_name: str) -> str | None:
    """Return the Polish vocative (singular) form of *first_name* via morfeusz2.

    Returns None when generation yields no singular vocative or on any error.
    Prefers forms tagged with a dedicated ':voc:' case over compound tags
    (e.g. 'nom.gen.dat.acc.inst.loc.voc') which indicate indeclinable surnames.
    """
    try:
        results = _morf.generate(first_name)
    except Exception:
        return None

    # Two-pass: first look for a dedicated vocative tag (e.g. "subst:sg:voc:m1"),
    # then fall back to compound tags that include 'voc'.
    fallback = None
    for result in results:
        surface, tag = result[0], result[2]
        parts = tag.split(":")
        if "sg" not in parts:
            continue
        # Check if 'voc' appears as a standalone case (not in a dot-joined group).
        case_parts = [p for p in parts if "." in p or p == "voc"]
        for cp in case_parts:
            cases = cp.split(".")
            if "voc" in cases:
                if cases == ["voc"]:
                    # Dedicated vocative — best match.
                    return surface
                if fallback is None:
                    fallback = surface
    return fallback


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
