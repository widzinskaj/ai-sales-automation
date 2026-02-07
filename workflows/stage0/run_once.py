"""Stage 0 — process new leads and send auto-reply emails.

Usage:
    python -m workflows.stage0.run_once
"""

from __future__ import annotations

import logging
import sys

from core import config
from core.lead_helpers import followup_due_formatted, is_new_lead, warsaw_now_formatted
from integrations.email_sender import send_auto_reply
from storage.sheets import SheetsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def process_lead_row(
    row: dict[str, str],
    row_number: int,
    sheets: SheetsClient,
    attachment_paths: list[str],
) -> bool:
    """Process a single new lead: send auto-reply and update the sheet.

    Returns True on success, False on failure.
    """
    lead_id = row.get("lead_id", "?")
    logger.info("Processing lead_id=%s (row %d)", lead_id, row_number)

    try:
        send_auto_reply(
            smtp_host=config.SMTP_HOST,
            smtp_port=config.SMTP_PORT,
            smtp_user=config.SMTP_USER,
            smtp_pass=config.SMTP_PASS,
            from_email=config.SMTP_FROM_EMAIL,
            from_name=config.SMTP_FROM_NAME,
            to_email=row["email"],
            full_name=row.get("full_name", ""),
            calendar_link=config.CALENDAR_LINK,
            attachment_paths=attachment_paths,
        )
    except Exception as exc:
        error_msg = str(exc)[:120]
        logger.error("Failed to send email for lead_id=%s: %s", lead_id, error_msg)
        sheets.update_row(row_number, {"auto_email_status": f"ERROR: {error_msg}"})
        return False

    sent_at = warsaw_now_formatted()
    sheets.update_row(row_number, {
        "auto_email_sent_at": sent_at,
        "auto_email_status": "OK",
        "followup_due_at": followup_due_formatted(sent_at),
        "followup_required": "NO",
    })
    return True


def main() -> None:
    logger.info("run_once: starting (env=%s)", config.APP_ENV)

    sheets = SheetsClient(
        service_account_json=config.GOOGLE_SERVICE_ACCOUNT_JSON,
        sheet_id=config.GOOGLE_SHEET_ID,
        tab_name=config.GOOGLE_SHEET_TAB,
    )

    # Apply date formatting once per run (idempotent).
    sheets.ensure_date_column_format()

    attachment_paths = [config.ATTACHMENT_A, config.ATTACHMENT_B, config.ATTACHMENT_C]
    rows = sheets.get_all_rows()
    processed = 0

    for idx, row in enumerate(rows):
        # Sheets row number: header is row 1, first data row is row 2.
        row_number = idx + 2

        if not is_new_lead(row):
            continue

        if process_lead_row(row, row_number, sheets, attachment_paths):
            processed += 1

    logger.info("run_once: done — %d lead(s) processed", processed)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("run_once failed")
        sys.exit(1)
