"""Stage 0 domain logic — follow-up scheduling.

Pure functions only.  No Google Sheets calls, no SMTP, no side effects.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")
_SHEET_DT_FMT = "%Y-%m-%d %H:%M"
_FOLLOWUP_DAYS = 3


class StatusRow(TypedDict, total=False):
    """One row in the Stage 0 status sheet.

    All timestamp values use the format ``YYYY-MM-DD HH:MM`` (Europe/Warsaw).
    A ``None`` (or absent) timestamp field means the event has not occurred yet.
    """

    email: str
    auto_email_sent_at: str | None
    auto_email_status: str
    followup_due_at: str | None
    followup_required: str
    followup_completed_at: str | None


def apply_followup_logic(status_row: StatusRow) -> StatusRow:
    """Apply follow-up scheduling rules to *status_row* and return the result.

    Rules (evaluated in order):

    1. ``auto_email_sent_at`` is ``None`` (or absent) →
       return *status_row* unchanged.
       (Email has not been sent yet; nothing to schedule.)

    2. ``followup_completed_at`` is not ``None`` →
       ensure ``followup_required = "NO"`` and return.
       (Follow-up is done; flag must reflect that.)

    3. ``followup_due_at`` is ``None`` (or absent) →
       set ``followup_due_at = auto_email_sent_at + 3 days``,
       set ``followup_required = "YES"``.
       (First-time scheduling.)

    4. Otherwise → return *status_row* unchanged.
       (Follow-up already scheduled; no action needed.)

    Guarantees:
    - **Pure** — no mutations, no I/O.
    - **Idempotent** — calling twice with the same row produces the same result.
    - Does not override an existing ``followup_due_at``.
    - Does not clear or modify ``followup_completed_at``.
    - Returns the *identical* input object when no update is required.
    """
    sent_at = status_row.get("auto_email_sent_at")
    if not sent_at:
        return status_row  # Rule 1 — email not sent yet

    # Rule 2 — follow-up already completed
    completed_at = status_row.get("followup_completed_at")
    if completed_at:
        if status_row.get("followup_required") == "NO":
            return status_row  # already correct — idempotent short-circuit
        return {**status_row, "followup_required": "NO"}  # type: ignore[return-value]

    # Rule 4 — already scheduled (check before trying to parse the date)
    if status_row.get("followup_due_at"):
        return status_row

    # Rule 3 — first-time scheduling
    try:
        sent_dt = datetime.strptime(sent_at, _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return status_row  # malformed timestamp — leave unchanged

    due_dt = sent_dt + timedelta(days=_FOLLOWUP_DAYS)
    return {  # type: ignore[return-value]
        **status_row,
        "followup_due_at": due_dt.strftime(_SHEET_DT_FMT),
        "followup_required": "YES",
    }
