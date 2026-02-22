"""Tests for Stage 0 retry eligibility logic.

Covers:
- is_eligible_for_send() unit tests (pure predicate, no I/O)
- Pipeline-level retry behaviour via process_new_leads() + mock sheets
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.stage0.process import process_new_leads
from src.storage.sheets import is_eligible_for_send

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CALENDAR_URL = "https://calendly.com/flexihome/konsultacja"
FAKE_ATTACHMENTS = [Path("a.pdf"), Path("b.pdf"), Path("c.pdf")]
LEAD_1 = {"Email": "test1@example.com", "Imię i nazwisko / Firma": "Anna Kowalska"}

FAKE_SMTP = dict(
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_user="user",
    smtp_password="pass",
    smtp_from_email="sender@example.com",
)


def _make_sheets(*, input_rows=None, new_leads=None, row_number=2):
    """Build a mocked SheetsClient (same pattern as test_process.py)."""
    client = MagicMock()
    client.read_input_rows.return_value = input_rows if input_rows is not None else []
    client.get_new_leads.return_value = new_leads if new_leads is not None else []
    client.ensure_status_rows_exist.return_value = None
    client.get_status_row_number_by_email.return_value = row_number
    return client


# ---------------------------------------------------------------------------
# Unit tests — is_eligible_for_send()
# ---------------------------------------------------------------------------

class TestIsEligibleForSend:
    """Pure predicate — no mocks needed."""

    def test_none_status_row_is_eligible(self):
        # Brand-new lead, no row in status sheet yet.
        assert is_eligible_for_send(None) is True

    def test_fresh_row_both_fields_empty_is_eligible(self):
        # Row was created by ensure_status_rows_exist() but never processed.
        row = {"auto_email_sent_at": "", "auto_email_status": ""}
        assert is_eligible_for_send(row) is True

    def test_error_without_sent_at_is_eligible(self):
        # Previous run wrote ERROR but did NOT write sent_at → safe to retry.
        row = {"auto_email_sent_at": "", "auto_email_status": "ERROR: SMTP timeout"}
        assert is_eligible_for_send(row) is True

    def test_error_with_sent_at_is_not_eligible(self):
        # sent_at is set — delivery was confirmed; ignore ERROR status.
        row = {"auto_email_sent_at": "2025-06-01 10:00", "auto_email_status": "ERROR: late write"}
        assert is_eligible_for_send(row) is False

    def test_sent_with_sent_at_is_not_eligible(self):
        row = {"auto_email_sent_at": "2025-06-01 10:00", "auto_email_status": "SENT"}
        assert is_eligible_for_send(row) is False

    def test_sent_at_whitespace_only_is_eligible(self):
        # Whitespace-only counts as empty — eligible.
        row = {"auto_email_sent_at": "   ", "auto_email_status": ""}
        assert is_eligible_for_send(row) is True

    def test_unknown_status_without_sent_at_is_not_eligible(self):
        # A future/unknown status value — conservative: do not retry.
        row = {"auto_email_sent_at": "", "auto_email_status": "PENDING"}
        assert is_eligible_for_send(row) is False

    def test_empty_dict_is_eligible(self):
        # Row with no fields — treated like a fresh row.
        assert is_eligible_for_send({}) is True

    def test_error_prefix_matched_case_sensitively(self):
        # Only "ERROR" prefix (uppercase) is treated as retryable.
        row = {"auto_email_sent_at": "", "auto_email_status": "error: smtp"}
        assert is_eligible_for_send(row) is False


# ---------------------------------------------------------------------------
# Pipeline tests (required by spec)
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """End-to-end pipeline behaviour — mocked Sheets + SMTP."""

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_error_with_sent_at_does_not_retry(self, mock_send, mock_build, mock_attach):
        """Lead with ERROR status but auto_email_sent_at already set → NOT retried.

        get_new_leads() correctly filters out the lead because is_eligible_for_send()
        returns False when sent_at is present. The mock reflects that filtered result.
        """
        mock_build.return_value = MagicMock(subject="s")
        # Eligibility check in get_new_leads() returns [] for this lead.
        sheets = _make_sheets(input_rows=[LEAD_1], new_leads=[])

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        mock_send.assert_not_called()
        assert report.emails_sent == 0
        assert report.emails_failed == 0

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_error_without_sent_at_retries_once_then_stops(self, mock_send, mock_build, mock_attach):
        """Lead with ERROR and no sent_at → email sent on first run, skipped on second.

        Run 1: get_new_leads() returns the lead (eligible — no sent_at).
               Pipeline sends the email and writes auto_email_sent_at.
        Run 2: get_new_leads() returns [] (sent_at now set → not eligible).
               Pipeline does nothing. Total send count stays at 1.
        """
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1], row_number=2)
        # Simulate two consecutive pipeline runs:
        # first call returns the error lead (eligible), second returns nothing.
        sheets.get_new_leads.side_effect = [[LEAD_1], []]

        first = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)
        second = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        # Exactly one send across both runs.
        assert mock_send.call_count == 1
        assert first.emails_sent == 1
        assert second.emails_sent == 0

        # auto_email_sent_at was written during the first (successful) run.
        _, updates = sheets.update_row.call_args_list[0][0]
        assert "auto_email_sent_at" in updates
        assert updates["auto_email_sent_at"] != ""
