"""Unit tests for src.stage0.process — no real Sheets, no real PDFs, no SMTP."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.stage0.process import ProcessReport, process_new_leads

CALENDAR_URL = "https://calendly.com/flexihome/konsultacja"

FAKE_ATTACHMENTS = [Path("a.pdf"), Path("b.pdf"), Path("c.pdf")]

LEAD_1 = {"Email": "test1@example.com", "Imię i nazwisko / Firma": "Anna Kowalska"}
LEAD_2 = {"Email": "test2@example.com", "Imię i nazwisko / Firma": "Marek Nowak"}

FAKE_SMTP = dict(
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_user="user",
    smtp_password="pass",
    smtp_from_email="sender@example.com",
)


def _make_sheets(*, input_rows=None, new_leads=None, row_number=2):
    """Build a mocked SheetsClient."""
    client = MagicMock()
    client.read_input_rows.return_value = input_rows if input_rows is not None else []
    client.get_new_leads.return_value = new_leads if new_leads is not None else []
    client.ensure_status_rows_exist.return_value = None
    client.get_status_row_number_by_email.return_value = row_number
    return client


# ---------------------------------------------------------------------------
# No new leads
# ---------------------------------------------------------------------------

class TestNoNewLeads:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_report_zeros(self, mock_send, mock_build, mock_attachments):
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], new_leads=[])

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        assert report == ProcessReport(
            total_input_leads=2,
            new_leads_detected=0,
            emails_sent=0,
            emails_failed=0,
        )
        mock_build.assert_not_called()
        mock_send.assert_not_called()

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_no_update_row_when_no_leads(self, mock_send, mock_build, mock_attachments):
        sheets = _make_sheets(new_leads=[])

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        sheets.update_row.assert_not_called()

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_ensure_status_rows_called_once(self, mock_send, mock_build, mock_attachments):
        sheets = _make_sheets(new_leads=[])

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        sheets.ensure_status_rows_exist.assert_called_once()


# ---------------------------------------------------------------------------
# Send success
# ---------------------------------------------------------------------------

class TestSendSuccess:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_update_row_called_with_sent_status(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1], row_number=3)

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        sheets.update_row.assert_called_once()
        row_num, updates = sheets.update_row.call_args[0]
        assert row_num == 3
        assert updates["auto_email_status"] == "SENT"
        assert "auto_email_sent_at" in updates

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_report_emails_sent(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], new_leads=[LEAD_1, LEAD_2])

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        assert report.emails_sent == 2
        assert report.emails_failed == 0

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_send_called_with_correct_email(self, mock_send, mock_build, mock_attachments):
        draft = MagicMock(subject="s")
        mock_build.return_value = draft
        sheets = _make_sheets(new_leads=[LEAD_1])

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        mock_send.assert_called_once_with(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
            from_email="sender@example.com",
            to_email="test1@example.com",
            draft=draft,
        )

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_sent_at_not_empty(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1])

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        _, updates = sheets.update_row.call_args[0]
        assert updates["auto_email_sent_at"] != ""


# ---------------------------------------------------------------------------
# Send failure
# ---------------------------------------------------------------------------

class TestSendFailure:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft", side_effect=RuntimeError("SMTP down"))
    def test_update_row_called_with_error_status(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1], row_number=2)

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        sheets.update_row.assert_called_once()
        _, updates = sheets.update_row.call_args[0]
        assert updates["auto_email_status"].startswith("ERROR:")
        assert "SMTP down" in updates["auto_email_status"]

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft", side_effect=RuntimeError("SMTP down"))
    def test_sent_at_not_written_on_failure(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1])

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        _, updates = sheets.update_row.call_args[0]
        assert "auto_email_sent_at" not in updates

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft", side_effect=RuntimeError("SMTP down"))
    def test_report_emails_failed(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1, LEAD_2])

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        assert report.emails_sent == 0
        assert report.emails_failed == 2


# ---------------------------------------------------------------------------
# Missing status row
# ---------------------------------------------------------------------------

class TestMissingStatusRow:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_no_update_and_failed_incremented(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1], row_number=None)

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        mock_send.assert_not_called()
        sheets.update_row.assert_not_called()
        assert report.emails_failed == 1
        assert report.emails_sent == 0


# ---------------------------------------------------------------------------
# Robustness: skip leads with missing/invalid email
# ---------------------------------------------------------------------------

class TestSkipsInvalidLeads:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_lead_with_empty_email_skipped(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        bad_lead = {"Email": "   ", "Imię i nazwisko / Firma": "Nieznany"}
        sheets = _make_sheets(new_leads=[bad_lead, LEAD_1])

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        assert mock_send.call_count == 1
        assert report.emails_sent == 1

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email", side_effect=ValueError("bad template"))
    @patch("src.stage0.process.send_email_draft")
    def test_build_exception_counted_as_failed(self, mock_send, mock_build, mock_attachments):
        sheets = _make_sheets(new_leads=[LEAD_1, LEAD_2])

        report = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        mock_send.assert_not_called()
        assert report.emails_sent == 0
        assert report.emails_failed == 2


# ---------------------------------------------------------------------------
# Idempotency: second call sees no new leads
# ---------------------------------------------------------------------------

class TestIdempotency:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_second_call_sends_zero(self, mock_send, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = MagicMock()
        sheets.read_input_rows.return_value = [LEAD_1, LEAD_2]
        sheets.ensure_status_rows_exist.return_value = None
        sheets.get_status_row_number_by_email.return_value = 2
        sheets.get_new_leads.side_effect = [[LEAD_1, LEAD_2], []]

        first = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)
        second = process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)

        assert first.emails_sent == 2
        assert second.emails_sent == 0
        assert sheets.ensure_status_rows_exist.call_count == 2
