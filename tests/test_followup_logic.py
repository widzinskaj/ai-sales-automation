"""Tests for src.stage0.followup — pure domain logic, no I/O required.

All calls to apply_followup_logic pass an explicit ``now`` so that test
results are deterministic and independent of wall-clock time.

Reference dates used throughout (Europe/Warsaw):
    SENT_AT      = "2025-06-01 10:00"
    DUE_AT       = "2025-06-04 10:00"   # SENT_AT + 3 days
    NOW_BEFORE   = 2025-06-02 10:00     # before DUE_AT
    NOW_AT_DUE   = 2025-06-04 10:00     # exactly at DUE_AT
    NOW_AFTER    = 2025-06-05 12:00     # after DUE_AT
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.stage0.followup import StatusRow, apply_followup_logic

WARSAW_TZ = ZoneInfo("Europe/Warsaw")

SENT_AT = "2025-06-01 10:00"
DUE_AT = "2025-06-04 10:00"

NOW_BEFORE = datetime(2025, 6, 2, 10, 0, tzinfo=WARSAW_TZ)   # 2 days before due
NOW_AT_DUE = datetime(2025, 6, 4, 10, 0, tzinfo=WARSAW_TZ)   # exactly at due
NOW_AFTER = datetime(2025, 6, 5, 12, 0, tzinfo=WARSAW_TZ)    # 1 day after due


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sent_row(**overrides: object) -> StatusRow:
    """Return a base StatusRow where the auto-reply was sent, nothing else set."""
    row: StatusRow = {
        "email": "test@example.com",
        "auto_email_sent_at": SENT_AT,
        "auto_email_status": "SENT",
        "followup_due_at": None,
        "followup_required": "",
        "followup_completed_at": None,
    }
    row.update(overrides)  # type: ignore[arg-type]
    return row


# ---------------------------------------------------------------------------
# First-time scheduling (Rule 3)
# ---------------------------------------------------------------------------

class TestFirstTimeScheduling:
    def test_sets_followup_due_at_plus_three_days(self):
        result = apply_followup_logic(_sent_row(), now=NOW_BEFORE)
        assert result["followup_due_at"] == DUE_AT

    def test_sets_followup_required_no_on_scheduling(self):
        """First-time scheduling sets required="NO" — not yet due at that moment."""
        result = apply_followup_logic(_sent_row(), now=NOW_BEFORE)
        assert result["followup_required"] == "NO"

    def test_preserves_all_other_fields(self):
        row = _sent_row()
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result["email"] == row["email"]
        assert result["auto_email_sent_at"] == row["auto_email_sent_at"]
        assert result["auto_email_status"] == row["auto_email_status"]
        assert result["followup_completed_at"] is None

    def test_year_boundary(self):
        now_before_newyear = datetime(2025, 12, 31, 10, 0, tzinfo=WARSAW_TZ)
        result = apply_followup_logic(
            _sent_row(auto_email_sent_at="2025-12-30 23:00"),
            now=now_before_newyear,
        )
        assert result["followup_due_at"] == "2026-01-02 23:00"

    def test_minute_precision_preserved(self):
        result = apply_followup_logic(
            _sent_row(auto_email_sent_at="2025-06-01 08:45"),
            now=NOW_BEFORE,
        )
        assert result["followup_due_at"] == "2025-06-04 08:45"

    def test_does_not_mutate_input(self):
        row = _sent_row()
        original_copy = dict(row)
        apply_followup_logic(row, now=NOW_BEFORE)
        assert dict(row) == original_copy


# ---------------------------------------------------------------------------
# Time-based evaluation (Rule 4)
# ---------------------------------------------------------------------------

class TestTimeBasedEvaluation:
    def test_before_due_sets_required_no(self):
        """now < due_at → followup_required must be "NO"."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result["followup_required"] == "NO"

    def test_at_due_sets_required_yes(self):
        """now == due_at (>= boundary) → followup_required must be "YES"."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="")
        result = apply_followup_logic(row, now=NOW_AT_DUE)
        assert result["followup_required"] == "YES"

    def test_after_due_sets_required_yes(self):
        """now > due_at → followup_required must be "YES"."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result["followup_required"] == "YES"

    def test_corrects_premature_yes_to_no(self):
        """If required is "YES" but now < due_at it must be corrected to "NO"."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="YES")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result["followup_required"] == "NO"

    def test_corrects_stale_no_to_yes_after_due(self):
        """If required is "NO" but now >= due_at it must be flipped to "YES"."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="NO")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result["followup_required"] == "YES"

    def test_does_not_override_existing_due_at(self):
        """Rule 4 never overwrites an existing due_at value."""
        row = _sent_row(followup_due_at="2025-09-01 09:00", followup_required="NO")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result["followup_due_at"] == "2025-09-01 09:00"

    def test_custom_due_at_not_recomputed(self):
        """A due date that differs from sent+3d is left untouched."""
        row = _sent_row(
            auto_email_sent_at=SENT_AT,
            followup_due_at="2025-06-10 10:00",  # 9 days, not 3
            followup_required="NO",
        )
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result["followup_due_at"] == "2025-06-10 10:00"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_not_due_yet_returns_unchanged(self):
        """Stable state: due_at set, required="NO", now before due → no change."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="NO")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row  # identical object — no copy made

    def test_past_due_returns_unchanged(self):
        """Stable state: due_at set, required="YES", now after due → no change."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="YES")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result == row

    def test_twice_gives_same_result_before_due(self):
        """Repeated calls with now before due_at are idempotent."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="NO")
        first = apply_followup_logic(row, now=NOW_BEFORE)
        second = apply_followup_logic(first, now=NOW_BEFORE)
        assert first == second

    def test_twice_gives_same_result_after_due(self):
        """Repeated calls with now after due_at are idempotent."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="YES")
        first = apply_followup_logic(row, now=NOW_AFTER)
        second = apply_followup_logic(first, now=NOW_AFTER)
        assert first == second

    def test_three_times_gives_same_result(self):
        """Three repeated calls with same now produce identical results."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="YES")
        r1 = apply_followup_logic(row, now=NOW_AFTER)
        r2 = apply_followup_logic(r1, now=NOW_AFTER)
        r3 = apply_followup_logic(r2, now=NOW_AFTER)
        assert r1 == r2 == r3


# ---------------------------------------------------------------------------
# Completed case (Rule 2)
# ---------------------------------------------------------------------------

class TestCompletedCase:
    def test_sets_followup_required_no(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result["followup_required"] == "NO"

    def test_preserves_completed_at(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result["followup_completed_at"] == "2025-06-03 15:00"

    def test_completed_idempotent(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00", followup_required="NO")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result is row

    def test_completed_takes_priority_over_missing_due_at(self):
        """Even when due_at is None, completed status must be applied first."""
        row = _sent_row(followup_completed_at="2025-06-03 15:00", followup_due_at=None)
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result["followup_required"] == "NO"
        # followup_due_at should NOT be set — completed rule returns early
        assert result.get("followup_due_at") is None

    def test_completed_does_not_mutate_input(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00")
        original_copy = dict(row)
        apply_followup_logic(row, now=NOW_AFTER)
        assert dict(row) == original_copy


# ---------------------------------------------------------------------------
# Missing / absent sent_at (Rule 1)
# ---------------------------------------------------------------------------

class TestMissingSentAt:
    def test_none_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at=None)
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_empty_string_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_whitespace_only_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="   ")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_absent_sent_at_key_returns_unchanged(self):
        row: StatusRow = {
            "email": "test@example.com",
            "auto_email_status": "",
            "followup_due_at": None,
            "followup_required": "",
            "followup_completed_at": None,
        }
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_none_sent_at_followup_due_not_set(self):
        row = _sent_row(auto_email_sent_at=None)
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result.get("followup_due_at") is None
        assert result.get("followup_required") == ""


# ---------------------------------------------------------------------------
# Malformed state safety
# ---------------------------------------------------------------------------

class TestMalformedStateSafety:
    def test_malformed_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="not-a-date")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_partial_date_no_time_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="2025-06-01")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_iso_with_seconds_returns_unchanged(self):
        """Format with seconds doesn't match _SHEET_DT_FMT — treat as malformed."""
        row = _sent_row(auto_email_sent_at="2025-06-01 10:00:00")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_garbage_value_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="!!!")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_malformed_due_at_returns_unchanged(self):
        """If due_at is present but unparseable, leave the row unchanged."""
        row = _sent_row(followup_due_at="not-a-date", followup_required="")
        result = apply_followup_logic(row, now=NOW_BEFORE)
        assert result is row

    def test_followup_required_is_string_yes(self):
        """followup_required must be the exact string "YES", not a boolean."""
        row = _sent_row(followup_due_at=DUE_AT, followup_required="YES")
        result = apply_followup_logic(row, now=NOW_AFTER)
        assert result["followup_required"] == "YES"
        assert isinstance(result["followup_required"], str)
