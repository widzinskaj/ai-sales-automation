"""Stage 0 — send auto-reply emails for new leads and persist status."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from src.email.attachments_stage0 import get_stage0_attachments_from_env
from src.email.template_stage0 import build_stage0_email
from src.integrations.email_sender import send_email_draft
from src.core.lead_helpers import generate_vocative, warsaw_now_formatted
from src.stage0.test_mode import resolve_recipient_email
from src.storage.sheets import SheetsClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessReport:
    total_input_leads: int
    new_leads_detected: int
    emails_sent: int
    emails_failed: int


def process_new_leads(
    sheets_client: SheetsClient,
    calendar_url: str,
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from_email: str,
    test_mode: bool = False,
    test_recipient: str | None = None,
) -> ProcessReport:
    """Send auto-reply emails for new leads and record status in the sheet.

    Side effects:
    - calls ensure_status_rows_exist() (structural sync, idempotent)
    - sends SMTP email per new lead
    - writes auto_email_sent_at / auto_email_status to status sheet

    When *test_mode* is True every outbound email is redirected to
    *test_recipient*.  If *test_recipient* is missing the function raises
    immediately before touching any data.
    """
    if test_mode:
        if not (test_recipient or "").strip():
            raise RuntimeError(
                "TEST_RECIPIENT_EMAIL is required when STAGE0_TEST_MODE=1. "
                "Set it to an internal address before running in test mode."
            )
        logger.info("TEST MODE active — recipient override in effect")

    sheets_client.ensure_status_rows_exist()

    input_rows = sheets_client.read_input_rows()
    new_leads = sheets_client.get_new_leads()

    attachments: list[Path] = get_stage0_attachments_from_env()

    emails_sent = 0
    emails_failed = 0

    for lead in new_leads:
        email = lead.get("Email", "").strip().lower()
        if not email:
            logger.warning("Skipping lead with missing email: %r", lead)
            continue

        full_name = lead.get("Imię i nazwisko / Firma", "")
        greeting = generate_vocative(full_name)

        try:
            draft = build_stage0_email(
                calendar_url=calendar_url,
                greeting=greeting,
                attachments=attachments,
            )
        except Exception:
            logger.exception("Failed to build draft for email=%s — skipping", email)
            emails_failed += 1
            continue

        row_number = sheets_client.get_status_row_number_by_email(email)
        if row_number is None:
            logger.error("Status row not found for email=%s — skipping", email)
            emails_failed += 1
            continue

        recipient = resolve_recipient_email(
            email, test_mode=test_mode, test_recipient=test_recipient
        )
        try:
            send_email_draft(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                from_email=smtp_from_email,
                to_email=recipient,
                draft=draft,
            )
        except Exception as exc:
            error_msg = str(exc)[:120]
            logger.error("Failed to send email to %s: %s", email, error_msg)
            sheets_client.update_row(row_number, {"auto_email_status": f"ERROR: {error_msg}"})
            emails_failed += 1
            continue

        sent_at = warsaw_now_formatted()
        sheets_client.update_row(row_number, {
            "auto_email_sent_at": sent_at,
            "auto_email_status": "SENT",
        })
        emails_sent += 1

    logger.info(
        "process_new_leads done — input=%d new=%d sent=%d failed=%d",
        len(input_rows),
        len(new_leads),
        emails_sent,
        emails_failed,
    )

    return ProcessReport(
        total_input_leads=len(input_rows),
        new_leads_detected=len(new_leads),
        emails_sent=emails_sent,
        emails_failed=emails_failed,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    from src.core import config  # lazy import — avoids config load during tests

    sheets = SheetsClient(
        service_account_json=config.GOOGLE_SERVICE_ACCOUNT_JSON,
        sheet_id=config.GOOGLE_SHEET_ID,
    )
    sheets.ensure_date_column_format()

    report = process_new_leads(
        sheets,
        config.CALENDAR_URL,
        smtp_host=config.SMTP_HOST,
        smtp_port=config.SMTP_PORT,
        smtp_user=config.SMTP_USER,
        smtp_password=config.SMTP_PASS,
        smtp_from_email=config.SMTP_FROM_EMAIL,
        test_mode=config.STAGE0_TEST_MODE,
        test_recipient=config.TEST_RECIPIENT_EMAIL,
    )
    logger.info("Done: %s", report)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("process_new_leads failed")
        sys.exit(1)
