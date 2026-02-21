"""Unit tests for core.lead_helpers — no network required."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.core.lead_helpers import (
    WARSAW_TZ,
    followup_due_formatted,
    generate_vocative,
    is_followup_due,
    is_new_lead,
    to_vocative_first_name,
    warsaw_now_formatted,
)


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
# generate_vocative
# ------------------------------------------------------------------

class TestGenerateVocative:
    def test_known_name_returns_personalised_greeting(self):
        # morfeusz2 knows "Anna" → vocative "Anno"
        assert generate_vocative("Anna Kowalska") == "Dzień dobry, Anno,"

    def test_known_male_name(self):
        # morfeusz2 knows "Marek" → vocative "Marku"
        assert generate_vocative("Marek Nowak") == "Dzień dobry, Marku,"

    def test_unknown_name_returns_fallback(self):
        # Nonsense token — morfeusz2 cannot generate a vocative
        assert generate_vocative("Xyzabc123 Whatever") == "Dzień dobry,"

    def test_empty_string_returns_fallback(self):
        assert generate_vocative("") == "Dzień dobry,"

    def test_whitespace_only_returns_fallback(self):
        assert generate_vocative("   ") == "Dzień dobry,"

    def test_company_like_string_returns_fallback(self):
        # First token "ACME" is not a Polish first name — fallback expected
        assert generate_vocative("ACME Sp. z o.o.") == "Dzień dobry,"

    def test_morfeusz_unavailable_returns_fallback(self):
        """When morfeusz2 cannot be initialised, fallback to plain greeting."""
        from unittest.mock import patch
        with patch("src.core.lead_helpers._get_morf", return_value=None):
            assert generate_vocative("Anna Kowalska") == "Dzień dobry,"
