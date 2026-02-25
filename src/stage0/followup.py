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


def apply_followup_logic(
    status_row: StatusRow,
    *,
    now: datetime | None = None,
) -> StatusRow:
    """Apply follow-up scheduling rules to *status_row* and return the result.

    Rules (evaluated in order):

    1. ``auto_email_sent_at`` is ``None`` / empty →
       return *status_row* unchanged.
       (Email has not been sent yet; nothing to schedule.)

    2. ``followup_completed_at`` is not ``None`` / empty →
       ensure ``followup_required = "NO"`` and return.
       (Follow-up is done; flag must reflect that regardless of due date.)

    3. ``followup_due_at`` is ``None`` / empty →
       set ``followup_due_at = auto_email_sent_at + 3 days``,
       set ``followup_required = "NO"`` (not yet due at scheduling time).
       (First-time scheduling.)

    4. ``followup_due_at`` is already set →
       compare *now* against ``followup_due_at``:
       - ``now >= followup_due_at`` → ``followup_required = "YES"``
       - ``now < followup_due_at``  → ``followup_required = "NO"``
       (Evaluate / correct the flag based on current time.)

    Guarantees:
    - **Pure** — no mutations, no I/O.
    - **Idempotent** — calling twice with the same row and the same *now*
      produces the same result.
    - Does not override an existing ``followup_due_at``.
    - Does not clear or modify ``followup_completed_at``.
    - Returns the *identical* input object when no update is required.
    - Malformed timestamps leave the row unchanged (conservative).

    Arguments:
        status_row: one row from the status sheet.
        now: reference time for due-date evaluation.  Defaults to
            ``datetime.now(WARSAW_TZ)`` when ``None``.
    """
    if now is None:
        now = datetime.now(WARSAW_TZ)

    # Rule 1 — email not sent yet
    sent_at_raw = status_row.get("auto_email_sent_at")
    if not str(sent_at_raw or "").strip():
        return status_row

    # Rule 2 — follow-up already completed
    completed_at = status_row.get("followup_completed_at")
    if completed_at:
        if status_row.get("followup_required") == "NO":
            return status_row  # already correct — idempotent short-circuit
        return {**status_row, "followup_required": "NO"}  # type: ignore[return-value]

    # Parse sent_at — shared by Rules 3 and 4
    try:
        sent_dt = datetime.strptime(str(sent_at_raw).strip(), _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return status_row  # malformed sent_at — leave unchanged

    existing_due_at_raw = status_row.get("followup_due_at")
    if not str(existing_due_at_raw or "").strip():
        # Rule 3 — first-time scheduling
        due_dt = sent_dt + timedelta(days=_FOLLOWUP_DAYS)
        return {  # type: ignore[return-value]
            **status_row,
            "followup_due_at": due_dt.strftime(_SHEET_DT_FMT),
            "followup_required": "NO",  # not due yet at scheduling time
        }

    # Rule 4 — due_at already set; evaluate against current time
    try:
        due_dt = datetime.strptime(
            str(existing_due_at_raw).strip(), _SHEET_DT_FMT
        ).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return status_row  # malformed due_at — leave unchanged

    expected = "YES" if now >= due_dt else "NO"
    if status_row.get("followup_required") == expected:
        return status_row  # already correct — idempotent short-circuit
    return {**status_row, "followup_required": expected}  # type: ignore[return-value]
