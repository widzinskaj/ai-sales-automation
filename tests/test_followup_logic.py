"""Tests for src.stage0.followup — pure domain logic, no I/O required."""

from __future__ import annotations

from src.stage0.followup import StatusRow, apply_followup_logic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sent_row(**overrides: object) -> StatusRow:
    """Return a base StatusRow where the auto-reply was sent, nothing else set."""
    row: StatusRow = {
        "email": "test@example.com",
        "auto_email_sent_at": "2025-06-01 10:00",
        "auto_email_status": "SENT",
        "followup_due_at": None,
        "followup_required": "",
        "followup_completed_at": None,
    }
    row.update(overrides)  # type: ignore[arg-type]
    return row


# ---------------------------------------------------------------------------
# First-time assignment
# ---------------------------------------------------------------------------

class TestFirstTimeAssignment:
    def test_sets_followup_due_at_plus_three_days(self):
        result = apply_followup_logic(_sent_row())
        assert result["followup_due_at"] == "2025-06-04 10:00"

    def test_sets_followup_required_yes(self):
        result = apply_followup_logic(_sent_row())
        assert result["followup_required"] == "YES"

    def test_preserves_all_other_fields(self):
        row = _sent_row()
        result = apply_followup_logic(row)
        assert result["email"] == row["email"]
        assert result["auto_email_sent_at"] == row["auto_email_sent_at"]
        assert result["auto_email_status"] == row["auto_email_status"]
        assert result["followup_completed_at"] is None

    def test_year_boundary(self):
        result = apply_followup_logic(_sent_row(auto_email_sent_at="2025-12-30 23:00"))
        assert result["followup_due_at"] == "2026-01-02 23:00"

    def test_minute_precision_preserved(self):
        result = apply_followup_logic(_sent_row(auto_email_sent_at="2025-06-01 08:45"))
        assert result["followup_due_at"] == "2025-06-04 08:45"

    def test_does_not_mutate_input(self):
        row = _sent_row()
        original_copy = dict(row)
        apply_followup_logic(row)
        assert dict(row) == original_copy


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_already_scheduled_returns_unchanged(self):
        row = _sent_row(followup_due_at="2025-06-04 10:00", followup_required="YES")
        result = apply_followup_logic(row)
        assert result == row

    def test_does_not_override_existing_due_at(self):
        row = _sent_row(followup_due_at="2025-09-01 09:00")
        result = apply_followup_logic(row)
        assert result["followup_due_at"] == "2025-09-01 09:00"

    def test_custom_due_at_not_recomputed(self):
        """A due date set to something other than sent+3d is left untouched."""
        row = _sent_row(
            auto_email_sent_at="2025-06-01 10:00",
            followup_due_at="2025-06-10 10:00",  # 9 days, not 3
        )
        result = apply_followup_logic(row)
        assert result["followup_due_at"] == "2025-06-10 10:00"

    def test_twice_gives_same_result(self):
        row = _sent_row()
        first = apply_followup_logic(row)
        second = apply_followup_logic(first)
        assert first == second

    def test_three_times_gives_same_result(self):
        row = _sent_row()
        r1 = apply_followup_logic(row)
        r2 = apply_followup_logic(r1)
        r3 = apply_followup_logic(r2)
        assert r1 == r2 == r3


# ---------------------------------------------------------------------------
# Completed case
# ---------------------------------------------------------------------------

class TestCompletedCase:
    def test_sets_followup_required_no(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00")
        result = apply_followup_logic(row)
        assert result["followup_required"] == "NO"

    def test_preserves_completed_at(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00")
        result = apply_followup_logic(row)
        assert result["followup_completed_at"] == "2025-06-03 15:00"

    def test_completed_idempotent(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00", followup_required="NO")
        result = apply_followup_logic(row)
        assert result == row

    def test_completed_takes_priority_over_missing_due_at(self):
        """Even when due_at is None, completed status must be applied first."""
        row = _sent_row(followup_completed_at="2025-06-03 15:00", followup_due_at=None)
        result = apply_followup_logic(row)
        assert result["followup_required"] == "NO"
        # followup_due_at should NOT be set — completed case returns early
        assert result.get("followup_due_at") is None

    def test_completed_does_not_mutate_input(self):
        row = _sent_row(followup_completed_at="2025-06-03 15:00")
        original_copy = dict(row)
        apply_followup_logic(row)
        assert dict(row) == original_copy


# ---------------------------------------------------------------------------
# Missing / absent sent_at
# ---------------------------------------------------------------------------

class TestMissingSentAt:
    def test_none_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at=None)
        result = apply_followup_logic(row)
        assert result == row

    def test_empty_string_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="")
        result = apply_followup_logic(row)
        assert result == row

    def test_whitespace_only_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="   ")
        result = apply_followup_logic(row)
        assert result == row

    def test_absent_sent_at_key_returns_unchanged(self):
        row: StatusRow = {
            "email": "test@example.com",
            "auto_email_status": "",
            "followup_due_at": None,
            "followup_required": "",
            "followup_completed_at": None,
        }
        result = apply_followup_logic(row)
        assert result == row

    def test_none_sent_at_followup_due_not_set(self):
        row = _sent_row(auto_email_sent_at=None)
        result = apply_followup_logic(row)
        assert result.get("followup_due_at") is None
        assert result.get("followup_required") == ""


# ---------------------------------------------------------------------------
# Malformed state safety
# ---------------------------------------------------------------------------

class TestMalformedStateSafety:
    def test_malformed_sent_at_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="not-a-date")
        result = apply_followup_logic(row)
        assert result == row

    def test_partial_date_no_time_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="2025-06-01")
        result = apply_followup_logic(row)
        assert result == row

    def test_iso_with_seconds_returns_unchanged(self):
        """Format with seconds doesn't match _SHEET_DT_FMT — treat as malformed."""
        row = _sent_row(auto_email_sent_at="2025-06-01 10:00:00")
        result = apply_followup_logic(row)
        assert result == row

    def test_garbage_value_returns_unchanged(self):
        row = _sent_row(auto_email_sent_at="!!!")
        result = apply_followup_logic(row)
        assert result == row

    def test_followup_required_is_string_yes(self):
        """followup_required must be the exact string "YES", not a boolean."""
        row = _sent_row(
            followup_due_at="2025-06-04 10:00",
            followup_required="YES",
        )
        result = apply_followup_logic(row)
        assert result["followup_required"] == "YES"
        assert isinstance(result["followup_required"], str)
