"""Tests for src.stage0.job — scheduler entrypoint.

Scenarios:
- Idempotency: N leads on run 1 → N sends; same job on run 2 → 0 sends.
- Test mode: all sends go to TEST_RECIPIENT_EMAIL, never to real lead.
- No PII in logs (spot-checked via caplog).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.core.config as _cfg
from src.stage0.job import run_stage0_job

# ---------------------------------------------------------------------------
# Shared test data (same conventions as test_process.py)
# ---------------------------------------------------------------------------

FAKE_ATTACHMENTS = [Path("a.pdf"), Path("b.pdf"), Path("c.pdf")]

LEAD_1 = {"Email": "lead-one@example.com", "Imię i nazwisko / Firma": "Anna Kowalska"}
LEAD_2 = {"Email": "lead-two@example.com", "Imię i nazwisko / Firma": "Marek Nowak"}
LEAD_3 = {"Email": "lead-three@example.com", "Imię i nazwisko / Firma": "Piotr Wiśniewski"}

TEST_ADDR = "test-inbox@internal.example.com"


def _make_sheets(*, input_rows=None, new_leads=None, row_number=2):
    """Build a mocked SheetsClient (same pattern as other stage0 tests)."""
    client = MagicMock()
    client.read_input_rows.return_value = input_rows if input_rows is not None else []
    client.get_new_leads.return_value = new_leads if new_leads is not None else []
    client.ensure_status_rows_exist.return_value = None
    client.get_status_row_number_by_email.return_value = row_number
    return client


# ---------------------------------------------------------------------------
# Idempotency: running the job twice must not send duplicate emails
# ---------------------------------------------------------------------------

class TestJobIdempotency:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_first_run_sends_for_all_new_leads(self, mock_send, mock_build, mock_attach):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2, LEAD_3], row_number=2)
        sheets.get_new_leads.return_value = [LEAD_1, LEAD_2, LEAD_3]

        report = run_stage0_job(sheets_client=sheets)

        assert report.emails_sent == 3
        assert report.emails_failed == 0
        assert mock_send.call_count == 3

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_second_run_sends_nothing(self, mock_send, mock_build, mock_attach):
        """After the first run auto_email_sent_at is written; the second run
        must see no eligible leads and make zero additional send calls."""
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(
            input_rows=[LEAD_1, LEAD_2],
            row_number=2,
        )
        # Simulate state transition: run 1 sees 2 leads, run 2 sees none.
        sheets.get_new_leads.side_effect = [[LEAD_1, LEAD_2], []]

        run1 = run_stage0_job(sheets_client=sheets)
        run2 = run_stage0_job(sheets_client=sheets)

        assert run1.emails_sent == 2
        assert run2.emails_sent == 0
        assert mock_send.call_count == 2  # total — no extra calls on run 2

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_second_run_does_not_update_sheet(self, mock_send, mock_build, mock_attach):
        """Second run: no sheet writes because there's nothing to send."""
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1], row_number=2)
        sheets.get_new_leads.side_effect = [[LEAD_1], []]

        run_stage0_job(sheets_client=sheets)   # run 1 — 1 update_row call
        update_calls_after_run1 = sheets.update_row.call_count
        run_stage0_job(sheets_client=sheets)   # run 2 — 0 extra update_row calls
        update_calls_after_run2 = sheets.update_row.call_count

        assert update_calls_after_run1 == 1
        assert update_calls_after_run2 == 1  # unchanged

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_reports_correct_counters_each_run(self, mock_send, mock_build, mock_attach):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], row_number=2)
        sheets.get_new_leads.side_effect = [[LEAD_1, LEAD_2], []]

        run1 = run_stage0_job(sheets_client=sheets)
        run2 = run_stage0_job(sheets_client=sheets)

        assert run1.new_leads_detected == 2
        assert run2.new_leads_detected == 0
        assert run2.total_input_leads == 2  # scanned same rows, just nothing to send


# ---------------------------------------------------------------------------
# Test mode: SMTP is called with TEST_RECIPIENT_EMAIL, not the lead address
# ---------------------------------------------------------------------------

class TestJobTestMode:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_test_mode_overrides_all_recipients(self, mock_send, mock_build, mock_attach):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1, LEAD_2], row_number=2)

        with patch.object(_cfg, "STAGE0_TEST_MODE", True), \
             patch.object(_cfg, "TEST_RECIPIENT_EMAIL", TEST_ADDR):
            run_stage0_job(sheets_client=sheets)

        assert mock_send.call_count == 2
        for call in mock_send.call_args_list:
            assert call.kwargs["to_email"] == TEST_ADDR
            assert call.kwargs["to_email"] not in (LEAD_1["Email"], LEAD_2["Email"])

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_test_mode_missing_recipient_raises_before_send(
        self, mock_send, mock_build, mock_attach
    ):
        sheets = _make_sheets(new_leads=[LEAD_1])

        with patch.object(_cfg, "STAGE0_TEST_MODE", True), \
             patch.object(_cfg, "TEST_RECIPIENT_EMAIL", None):
            with pytest.raises(RuntimeError, match="TEST_RECIPIENT_EMAIL"):
                run_stage0_job(sheets_client=sheets)

        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Logging: start / complete lines, no PII (spot-check via caplog)
# ---------------------------------------------------------------------------

class TestJobLogging:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_logs_start_and_complete(self, mock_send, mock_build, mock_attach, caplog):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1])

        with caplog.at_level("INFO", logger="src.stage0.job"):
            run_stage0_job(sheets_client=sheets)

        messages = [r.message for r in caplog.records if r.name == "src.stage0.job"]
        assert any("Stage0 job start" in m for m in messages)
        assert any("Stage0 job complete" in m for m in messages)

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_complete_log_contains_counters(self, mock_send, mock_build, mock_attach, caplog):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(input_rows=[LEAD_1, LEAD_2], new_leads=[LEAD_1, LEAD_2])

        with caplog.at_level("INFO", logger="src.stage0.job"):
            run_stage0_job(sheets_client=sheets)

        complete_msgs = [
            r.message for r in caplog.records
            if r.name == "src.stage0.job" and "complete" in r.message
        ]
        assert complete_msgs, "Expected a 'complete' log line"
        line = complete_msgs[0]
        # Counters present, no lead email addresses in job-level logs.
        assert "sent=2" in line
        assert "lead-one@example.com" not in line
        assert "lead-two@example.com" not in line

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_test_mode_logged_at_job_level(self, mock_send, mock_build, mock_attach, caplog):
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[])

        with patch.object(_cfg, "STAGE0_TEST_MODE", True), \
             patch.object(_cfg, "TEST_RECIPIENT_EMAIL", TEST_ADDR):
            with caplog.at_level("INFO", logger="src.stage0.job"):
                run_stage0_job(sheets_client=sheets)

        messages = [r.message for r in caplog.records if r.name == "src.stage0.job"]
        assert any("TEST MODE" in m for m in messages)
        # The test recipient itself must not appear in job-level logs.
        assert all(TEST_ADDR not in m for m in messages)
