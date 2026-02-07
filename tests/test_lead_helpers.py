"""Unit tests for core.lead_helpers and workflow orchestration — no network required."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from core.lead_helpers import (
    WARSAW_TZ,
    followup_due_formatted,
    is_followup_due,
    is_new_lead,
    to_vocative_first_name,
    warsaw_now_formatted,
)
from integrations.email_sender import build_greeting
from workflows.stage0.run_once import process_lead_row


# ------------------------------------------------------------------
# is_new_lead
# ------------------------------------------------------------------

class TestIsNewLead:
    def test_new_lead_with_email_and_no_sent(self):
        row = {"email": "x@example.com", "auto_email_sent_at": ""}
        assert is_new_lead(row) is True

    def test_already_processed(self):
        row = {"email": "x@example.com", "auto_email_sent_at": "2025-01-01 10:00"}
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
# warsaw_now_formatted
# ------------------------------------------------------------------

class TestWarsawNowFormatted:
    def test_format_yyyy_mm_dd_hh_mm(self):
        result = warsaw_now_formatted()
        # Should match YYYY-MM-DD HH:MM (16 chars)
        assert len(result) == 16
        parsed = datetime.strptime(result, "%Y-%m-%d %H:%M")
        assert parsed is not None

    def test_no_seconds(self):
        result = warsaw_now_formatted()
        # Exactly two colons would mean seconds are present; we expect one.
        assert result.count(":") == 1


# ------------------------------------------------------------------
# followup_due_formatted
# ------------------------------------------------------------------

class TestFollowupDueFormatted:
    def test_adds_three_days(self):
        assert followup_due_formatted("2025-06-01 12:00") == "2025-06-04 12:00"

    def test_custom_days(self):
        assert followup_due_formatted("2025-06-01 12:00", days=7) == "2025-06-08 12:00"

    def test_format_preserved(self):
        result = followup_due_formatted("2025-12-30 23:45")
        assert len(result) == 16
        assert result.count(":") == 1


# ------------------------------------------------------------------
# is_followup_due
# ------------------------------------------------------------------

class TestIsFollowupDue:
    def _past(self, hours: int = 1) -> str:
        return (datetime.now(WARSAW_TZ) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")

    def _future(self, days: int = 1) -> str:
        return (datetime.now(WARSAW_TZ) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")

    def test_due_in_past_not_yet_marked(self):
        row = {"followup_due_at": self._past(), "followup_required": ""}
        assert is_followup_due(row) is True

    def test_due_in_future(self):
        row = {"followup_due_at": self._future(), "followup_required": ""}
        assert is_followup_due(row) is False

    def test_already_marked_yes(self):
        row = {"followup_due_at": self._past(), "followup_required": "YES"}
        assert is_followup_due(row) is False

    def test_empty_due_at(self):
        row = {"followup_due_at": "", "followup_required": ""}
        assert is_followup_due(row) is False

    def test_missing_keys(self):
        assert is_followup_due({}) is False

    def test_case_insensitive_yes(self):
        row = {"followup_due_at": self._past(), "followup_required": "yes"}
        assert is_followup_due(row) is False

    def test_no_value_not_blocking(self):
        row = {"followup_due_at": self._past(), "followup_required": "NO"}
        assert is_followup_due(row) is True


# ------------------------------------------------------------------
# to_vocative_first_name
# ------------------------------------------------------------------

class TestToVocativeFirstName:
    def test_anna(self):
        assert to_vocative_first_name("Anna") == "Anno"

    def test_marek(self):
        assert to_vocative_first_name("Marek") == "Marku"

    def test_kuba(self):
        assert to_vocative_first_name("Kuba") == "Kubo"

    def test_agnieszka(self):
        assert to_vocative_first_name("Agnieszka") == "Agnieszko"

    def test_tomasz(self):
        assert to_vocative_first_name("Tomasz") == "Tomaszu"

    def test_unknown_returns_none(self):
        assert to_vocative_first_name("Xyzabc123") is None

    def test_empty_returns_none(self):
        assert to_vocative_first_name("") is None


# ------------------------------------------------------------------
# build_greeting (vocative, end-to-end)
# ------------------------------------------------------------------

class TestBuildGreeting:
    def test_feminine_vocative(self):
        assert build_greeting("Anna Kowalska") == "Dzień dobry, Pani Anno,"

    def test_masculine_vocative(self):
        assert build_greeting("Marek Nowak") == "Dzień dobry, Panie Marku,"

    def test_masculine_exception_vocative(self):
        assert build_greeting("Kuba Wiśniewski") == "Dzień dobry, Panie Kubo,"

    def test_unknown_name_fallback(self):
        assert build_greeting("Xyzabc Qwerty") == "Dzień dobry,"

    def test_empty_name(self):
        assert build_greeting("") == "Dzień dobry,"

    def test_none_name(self):
        assert build_greeting(None) == "Dzień dobry,"


# ------------------------------------------------------------------
# process_lead_row — SMTP failure path
# ------------------------------------------------------------------

class TestProcessLeadRowSmtpFailure:
    """Verify that an SMTP error writes ERROR status and leaves the lead retryable."""

    _ROW = {
        "lead_id": "test-123",
        "email": "x@example.com",
        "full_name": "Anna Kowalska",
        "auto_email_sent_at": "",
    }

    @patch("workflows.stage0.run_once.send_auto_reply", side_effect=RuntimeError("SMTP down"))
    def test_sets_error_status(self, _mock_send: MagicMock) -> None:
        spy = MagicMock()
        result = process_lead_row(self._ROW, row_number=2, sheets=spy, attachment_paths=[])

        assert result is False
        spy.update_row.assert_called_once()
        _, kwargs = spy.update_row.call_args
        updates = kwargs.get("updates") or spy.update_row.call_args[0][1]
        assert "auto_email_status" in updates
        assert updates["auto_email_status"].startswith("ERROR:")
        assert "SMTP down" in updates["auto_email_status"]

    @patch("workflows.stage0.run_once.send_auto_reply", side_effect=RuntimeError("SMTP down"))
    def test_does_not_set_sent_at(self, _mock_send: MagicMock) -> None:
        spy = MagicMock()
        process_lead_row(self._ROW, row_number=2, sheets=spy, attachment_paths=[])

        updates = spy.update_row.call_args[0][1]
        assert "auto_email_sent_at" not in updates

    @patch("workflows.stage0.run_once.send_auto_reply", side_effect=RuntimeError("SMTP down"))
    def test_lead_remains_retryable(self, _mock_send: MagicMock) -> None:
        spy = MagicMock()
        process_lead_row(self._ROW, row_number=2, sheets=spy, attachment_paths=[])

        # auto_email_sent_at was not written, so the lead stays new.
        assert is_new_lead(self._ROW) is True

    @patch("workflows.stage0.run_once.send_auto_reply")
    def test_success_path_sets_all_fields(self, _mock_send: MagicMock) -> None:
        spy = MagicMock()
        result = process_lead_row(self._ROW, row_number=2, sheets=spy, attachment_paths=[])

        assert result is True
        updates = spy.update_row.call_args[0][1]
        assert updates["auto_email_status"] == "OK"
        assert "auto_email_sent_at" in updates
        assert "followup_due_at" in updates
        assert updates["followup_required"] == "NO"
