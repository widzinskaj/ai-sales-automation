"""Stage 0 domain logic — follow-up scheduling.

Pure functions only.  No Google Sheets calls, no SMTP, no side effects.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")
_SHEET_DT_FMT = "%Y-%m-%d %H:%M"
_FOLLOWUP_DAYS = 3

# Type alias for a status sheet row.
# Keys match the sheet column headers (e.g. "Email wysłany", "Follow-up od").
StatusRow = dict[str, str | None]


def apply_followup_logic(
    status_row: StatusRow,
    *,
    now: datetime | None = None,
) -> StatusRow:
    """Apply follow-up scheduling rules to *status_row* and return the result.

    Rules (evaluated in order):

    1. ``Email wysłany`` is ``None`` / empty →
       return *status_row* unchanged.
       (Email has not been sent yet; nothing to schedule.)

    2. ``Follow-up wykonany`` is not ``None`` / empty →
       ensure ``Wymaga follow-upu = "NO"`` and return.
       (Follow-up is done; flag must reflect that regardless of due date.)

    3. ``Follow-up od`` is ``None`` / empty →
       set ``Follow-up od = Email wysłany + 3 days``,
       set ``Wymaga follow-upu = "NO"`` (not yet due at scheduling time).
       (First-time scheduling.)

    4. ``Follow-up od`` is already set →
       compare *now* against ``Follow-up od``:
       - ``now >= Follow-up od`` → ``Wymaga follow-upu = "YES"``
       - ``now < Follow-up od``  → ``Wymaga follow-upu = "NO"``
       (Evaluate / correct the flag based on current time.)

    Guarantees:
    - **Pure** — no mutations, no I/O.
    - **Idempotent** — calling twice with the same row and the same *now*
      produces the same result.
    - Does not override an existing ``Follow-up od``.
    - Does not clear or modify ``Follow-up wykonany``.
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
    sent_at_raw = status_row.get("Email wysłany")
    if not str(sent_at_raw or "").strip():
        return status_row

    # Rule 2 — follow-up already completed
    completed_at = status_row.get("Follow-up wykonany")
    if completed_at:
        if status_row.get("Wymaga follow-upu") == "NO":
            return status_row  # already correct — idempotent short-circuit
        return {**status_row, "Wymaga follow-upu": "NO"}  # type: ignore[return-value]

    # Parse sent_at — shared by Rules 3 and 4
    try:
        sent_dt = datetime.strptime(str(sent_at_raw).strip(), _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return status_row  # malformed sent_at — leave unchanged

    existing_due_at_raw = status_row.get("Follow-up od")
    if not str(existing_due_at_raw or "").strip():
        # Rule 3 — first-time scheduling
        due_dt = sent_dt + timedelta(days=_FOLLOWUP_DAYS)
        return {  # type: ignore[return-value]
            **status_row,
            "Follow-up od": due_dt.strftime(_SHEET_DT_FMT),
            "Wymaga follow-upu": "NO",  # not due yet at scheduling time
        }

    # Rule 4 — due_at already set; evaluate against current time
    try:
        due_dt = datetime.strptime(
            str(existing_due_at_raw).strip(), _SHEET_DT_FMT
        ).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return status_row  # malformed due_at — leave unchanged

    expected = "YES" if now >= due_dt else "NO"
    if status_row.get("Wymaga follow-upu") == expected:
        return status_row  # already correct — idempotent short-circuit
    return {**status_row, "Wymaga follow-upu": expected}  # type: ignore[return-value]
