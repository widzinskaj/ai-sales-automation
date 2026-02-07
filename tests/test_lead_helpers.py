"""Unit tests for core.lead_helpers — no network required."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.lead_helpers import (
    followup_due_iso,
    is_followup_due,
    is_new_lead,
    utc_now_iso,
)


# ------------------------------------------------------------------
# is_new_lead
# ------------------------------------------------------------------

class TestIsNewLead:
    def test_new_lead_with_email_and_no_sent(self):
        row = {"email": "x@example.com", "auto_email_sent_at": ""}
        assert is_new_lead(row) is True

    def test_already_processed(self):
        row = {"email": "x@example.com", "auto_email_sent_at": "2025-01-01T00:00:00+00:00"}
        assert is_new_lead(row) is False

    def test_missing_email(self):
        row = {"email": "", "auto_email_sent_at": ""}
        assert is_new_lead(row) is False

    def test_whitespace_only_email(self):
        row = {"email": "  ", "auto_email_sent_at": ""}
        assert is_new_lead(row) is False

    def test_missing_keys_treated_as_empty(self):
        assert is_new_lead({}) is False

    def test_whitespace_only_sent_at_is_new(self):
        row = {"email": "x@example.com", "auto_email_sent_at": "  "}
        assert is_new_lead(row) is True


# ------------------------------------------------------------------
# utc_now_iso
# ------------------------------------------------------------------

class TestUtcNowIso:
    def test_format_is_valid_iso(self):
        result = utc_now_iso()
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None

    def test_no_microseconds(self):
        result = utc_now_iso()
        assert "." not in result


# ------------------------------------------------------------------
# followup_due_iso
# ------------------------------------------------------------------

class TestFollowupDueIso:
    def test_adds_three_days(self):
        sent = "2025-06-01T12:00:00+00:00"
        due = followup_due_iso(sent)
        assert due == "2025-06-04T12:00:00+00:00"

    def test_custom_days(self):
        sent = "2025-06-01T12:00:00+00:00"
        due = followup_due_iso(sent, days=7)
        assert due == "2025-06-08T12:00:00+00:00"

    def test_no_microseconds(self):
        sent = "2025-06-01T12:00:00.123456+00:00"
        due = followup_due_iso(sent)
        assert "." not in due


# ------------------------------------------------------------------
# is_followup_due
# ------------------------------------------------------------------

class TestIsFollowupDue:
    def test_due_in_past_not_yet_marked(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        row = {"followup_due_at": past, "followup_required": ""}
        assert is_followup_due(row) is True

    def test_due_in_future(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        row = {"followup_due_at": future, "followup_required": ""}
        assert is_followup_due(row) is False

    def test_already_marked_true(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        row = {"followup_due_at": past, "followup_required": "TRUE"}
        assert is_followup_due(row) is False

    def test_empty_due_at(self):
        row = {"followup_due_at": "", "followup_required": ""}
        assert is_followup_due(row) is False

    def test_missing_keys(self):
        assert is_followup_due({}) is False

    def test_case_insensitive_true(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        row = {"followup_due_at": past, "followup_required": "true"}
        assert is_followup_due(row) is False
