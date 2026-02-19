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


def _make_sheets(*, input_rows=None, new_leads=None):
    """Build a mocked SheetsClient."""
    client = MagicMock()
    client.read_input_rows.return_value = input_rows if input_rows is not None else []
    client.get_new_leads.return_value = new_leads if new_leads is not None else []
    client.ensure_status_rows_exist.return_value = None
    return client


# ---------------------------------------------------------------------------
# No new leads
# ---------------------------------------------------------------------------

class TestNoNewLeads:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_report_drafts_zero(self, mock_build, mock_attachments):
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], new_leads=[])

        report = process_new_leads(sheets, CALENDAR_URL)

        assert report == ProcessReport(
            total_input_leads=2,
            new_leads_detected=0,
            drafts_built=0,
        )
        mock_build.assert_not_called()

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_ensure_status_rows_called_once(self, mock_build, mock_attachments):
        sheets = _make_sheets(new_leads=[])

        process_new_leads(sheets, CALENDAR_URL)

        sheets.ensure_status_rows_exist.assert_called_once()


# ---------------------------------------------------------------------------
# Two new leads
# ---------------------------------------------------------------------------

class TestTwoNewLeads:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_build_called_twice(self, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="Test subject")
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], new_leads=[LEAD_1, LEAD_2])

        report = process_new_leads(sheets, CALENDAR_URL)

        assert mock_build.call_count == 2
        assert report.drafts_built == 2

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_build_receives_correct_args(self, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="Test subject")
        sheets = _make_sheets(new_leads=[LEAD_1])

        process_new_leads(sheets, CALENDAR_URL)

        mock_build.assert_called_once_with(
            calendar_url=CALENDAR_URL,
            attachments=FAKE_ATTACHMENTS,
        )

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_report_counts(self, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], new_leads=[LEAD_1, LEAD_2])

        report = process_new_leads(sheets, CALENDAR_URL)

        assert report == ProcessReport(
            total_input_leads=2,
            new_leads_detected=2,
            drafts_built=2,
        )


# ---------------------------------------------------------------------------
# Idempotency: second call sees no new leads
# ---------------------------------------------------------------------------

class TestIdempotency:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_second_call_builds_zero_drafts(self, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        sheets = MagicMock()
        sheets.read_input_rows.return_value = [LEAD_1, LEAD_2]
        sheets.ensure_status_rows_exist.return_value = None
        # First call sees 2 new leads, second call sees none
        sheets.get_new_leads.side_effect = [[LEAD_1, LEAD_2], []]

        first = process_new_leads(sheets, CALENDAR_URL)
        second = process_new_leads(sheets, CALENDAR_URL)

        assert first.drafts_built == 2
        assert second.drafts_built == 0
        assert sheets.ensure_status_rows_exist.call_count == 2


# ---------------------------------------------------------------------------
# Robustness: skip lead with missing email
# ---------------------------------------------------------------------------

class TestSkipsInvalidLeads:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    def test_lead_with_empty_email_skipped(self, mock_build, mock_attachments):
        mock_build.return_value = MagicMock(subject="s")
        bad_lead = {"Email": "   ", "Imię i nazwisko / Firma": "Nieznany"}
        sheets = _make_sheets(new_leads=[bad_lead, LEAD_1])

        report = process_new_leads(sheets, CALENDAR_URL)

        # Only LEAD_1 should produce a draft
        assert mock_build.call_count == 1
        assert report.drafts_built == 1

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email", side_effect=ValueError("bad"))
    def test_build_exception_skipped_no_crash(self, mock_build, mock_attachments):
        sheets = _make_sheets(new_leads=[LEAD_1, LEAD_2])

        report = process_new_leads(sheets, CALENDAR_URL)

        assert report.drafts_built == 0
