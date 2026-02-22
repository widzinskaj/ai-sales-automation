"""Tests for Stage 0 test-mode hardening.

Covers:
- resolve_recipient_email() unit tests (pure function, no I/O)
- process_new_leads() integration behaviour in test mode (mocked Sheets + SMTP)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.stage0.process import process_new_leads
from src.stage0.test_mode import resolve_recipient_email

# ---------------------------------------------------------------------------
# Shared fixtures (same pattern as test_process.py)
# ---------------------------------------------------------------------------

CALENDAR_URL = "https://calendly.com/flexihome/konsultacja"
FAKE_ATTACHMENTS = [Path("a.pdf"), Path("b.pdf"), Path("c.pdf")]

LEAD_1 = {"Email": "real-lead@example.com", "Imię i nazwisko / Firma": "Anna Kowalska"}
LEAD_2 = {"Email": "other-lead@example.com", "Imię i nazwisko / Firma": "Marek Nowak"}

TEST_ADDR = "test-inbox@internal.example.com"

FAKE_SMTP = dict(
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_user="user",
    smtp_password="pass",
    smtp_from_email="sender@example.com",
)


def _make_sheets(*, input_rows=None, new_leads=None, row_number=2):
    client = MagicMock()
    client.read_input_rows.return_value = input_rows if input_rows is not None else []
    client.get_new_leads.return_value = new_leads if new_leads is not None else []
    client.ensure_status_rows_exist.return_value = None
    client.get_status_row_number_by_email.return_value = row_number
    return client


# ---------------------------------------------------------------------------
# Unit tests — resolve_recipient_email()
# ---------------------------------------------------------------------------

class TestResolveRecipientEmail:
    # ---- test mode: raises when test_recipient is missing or blank ----

    def test_test_mode_requires_test_recipient(self):
        with pytest.raises(RuntimeError, match="TEST_RECIPIENT_EMAIL"):
            resolve_recipient_email("lead@example.com", test_mode=True, test_recipient=None)

    def test_test_mode_requires_nonempty_test_recipient(self):
        with pytest.raises(RuntimeError, match="TEST_RECIPIENT_EMAIL"):
            resolve_recipient_email("lead@example.com", test_mode=True, test_recipient="")

    def test_test_mode_requires_nonblank_test_recipient(self):
        with pytest.raises(RuntimeError, match="TEST_RECIPIENT_EMAIL"):
            resolve_recipient_email("lead@example.com", test_mode=True, test_recipient="   ")

    # ---- test mode: overrides recipient ----

    def test_test_mode_overrides_recipient(self):
        result = resolve_recipient_email(
            "real-lead@example.com", test_mode=True, test_recipient=TEST_ADDR
        )
        assert result == TEST_ADDR

    def test_test_mode_result_is_not_lead_email(self):
        result = resolve_recipient_email(
            "real-lead@example.com", test_mode=True, test_recipient=TEST_ADDR
        )
        assert result != "real-lead@example.com"

    def test_test_mode_strips_and_lowercases_test_recipient(self):
        result = resolve_recipient_email(
            "lead@example.com", test_mode=True, test_recipient="  Test@INTERNAL.com  "
        )
        assert result == "test@internal.com"

    # ---- normal mode: uses lead email ----

    def test_non_test_mode_uses_lead_email(self):
        result = resolve_recipient_email(
            "lead@example.com", test_mode=False, test_recipient=None
        )
        assert result == "lead@example.com"

    def test_non_test_mode_ignores_test_recipient(self):
        result = resolve_recipient_email(
            "lead@example.com", test_mode=False, test_recipient=TEST_ADDR
        )
        assert result == "lead@example.com"

    def test_non_test_mode_does_not_raise_without_test_recipient(self):
        # Must not raise even when test_recipient is absent in normal mode.
        result = resolve_recipient_email(
            "lead@example.com", test_mode=False, test_recipient=None
        )
        assert result == "lead@example.com"


# ---------------------------------------------------------------------------
# Integration tests — process_new_leads() in test mode
# ---------------------------------------------------------------------------

class TestTestModeProcessIntegration:
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_test_mode_sends_to_test_recipient_not_lead(
        self, mock_send, mock_build, mock_attach
    ):
        """In test mode the SMTP sender is called with TEST_RECIPIENT_EMAIL,
        never with the lead's real address."""
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1], row_number=2)

        process_new_leads(
            sheets, CALENDAR_URL, **FAKE_SMTP,
            test_mode=True,
            test_recipient=TEST_ADDR,
        )

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == TEST_ADDR
        assert mock_send.call_args.kwargs["to_email"] != LEAD_1["Email"]

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_test_mode_multiple_leads_all_go_to_test_recipient(
        self, mock_send, mock_build, mock_attach
    ):
        """All leads share the same test recipient — no real address leaks."""
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1, LEAD_2], row_number=2)

        process_new_leads(
            sheets, CALENDAR_URL, **FAKE_SMTP,
            test_mode=True,
            test_recipient=TEST_ADDR,
        )

        assert mock_send.call_count == 2
        for call in mock_send.call_args_list:
            assert call.kwargs["to_email"] == TEST_ADDR

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_test_mode_raises_at_startup_if_no_test_recipient(
        self, mock_send, mock_build, mock_attach
    ):
        """process_new_leads must raise before doing any work when test_mode=True
        but test_recipient is missing — fail fast."""
        sheets = _make_sheets(new_leads=[LEAD_1])

        with pytest.raises(RuntimeError, match="TEST_RECIPIENT_EMAIL"):
            process_new_leads(
                sheets, CALENDAR_URL, **FAKE_SMTP,
                test_mode=True,
                test_recipient=None,
            )

        # Nothing should have been called before the error.
        mock_send.assert_not_called()
        sheets.ensure_status_rows_exist.assert_not_called()

    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    @patch("src.stage0.process.build_stage0_email")
    @patch("src.stage0.process.send_email_draft")
    def test_normal_mode_uses_lead_email(self, mock_send, mock_build, mock_attach):
        """Without test mode, lead email is used as-is."""
        mock_build.return_value = MagicMock(subject="s")
        sheets = _make_sheets(new_leads=[LEAD_1], row_number=2)

        process_new_leads(sheets, CALENDAR_URL, **FAKE_SMTP)  # test_mode defaults to False

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == LEAD_1["Email"].lower()
