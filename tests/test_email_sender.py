"""Unit tests for integrations.email_sender — no network required."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.email.template_stage0 import EmailDraft
from src.integrations.email_sender import send_email_draft

FAKE_DRAFT = EmailDraft(
    subject="Test subject",
    body="Test body",
    attachments=[],
)


class TestSendEmailDraft:
    def test_sends_via_smtp(self):
        """Happy path: send_message is called once with correct headers."""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_server

            send_email_draft(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_user="user@example.com",
                smtp_password="secret",
                from_email="sender@example.com",
                to_email="recipient@example.com",
                draft=FAKE_DRAFT,
            )

        mock_server.send_message.assert_called_once()
        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["Subject"] == "Test subject"
        assert sent_msg["To"] == "recipient@example.com"
        assert sent_msg["From"] == "sender@example.com"

    def test_starttls_and_login_called(self):
        """STARTTLS upgrade and login must always be performed."""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_server

            send_email_draft(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_user="user",
                smtp_password="pass",
                from_email="f@x.com",
                to_email="t@x.com",
                draft=FAKE_DRAFT,
            )

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")

    def test_raises_on_missing_attachment(self, tmp_path):
        """FileNotFoundError raised before SMTP connection is attempted."""
        draft_with_missing = EmailDraft(
            subject="s",
            body="b",
            attachments=[tmp_path / "nonexistent.pdf"],
        )
        with patch("smtplib.SMTP") as mock_smtp_cls:
            with pytest.raises(FileNotFoundError, match="nonexistent.pdf"):
                send_email_draft(
                    smtp_host="h",
                    smtp_port=587,
                    smtp_user="u",
                    smtp_password="p",
                    from_email="f@x.com",
                    to_email="t@x.com",
                    draft=draft_with_missing,
                )
        mock_smtp_cls.assert_not_called()

    def test_attaches_pdf(self, tmp_path):
        """Attachment file is included in the MIME message."""
        pdf = tmp_path / "offer.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        draft_with_pdf = EmailDraft(subject="s", body="b", attachments=[pdf])

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_server

            send_email_draft(
                smtp_host="h",
                smtp_port=587,
                smtp_user="u",
                smtp_password="p",
                from_email="f@x.com",
                to_email="t@x.com",
                draft=draft_with_pdf,
            )

        sent_msg = mock_server.send_message.call_args[0][0]
        payloads = sent_msg.get_payload()
        filenames = [p.get_filename() for p in payloads if p.get_filename()]
        assert "offer.pdf" in filenames
