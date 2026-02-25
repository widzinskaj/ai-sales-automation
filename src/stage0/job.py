"""Stage 0 — official scheduler entrypoint.

A single, stable function to be triggered by cron / task-scheduler.
Wraps process_new_leads() with structured, PII-safe logging and
config loading.  Accepts an optional pre-built SheetsClient so the
function is testable without live credentials.

Usage (production):
    python -m src.stage0.job
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from src.stage0.process import ProcessReport, process_followups, process_new_leads

if TYPE_CHECKING:
    from src.storage.sheets import SheetsClient

logger = logging.getLogger(__name__)


def run_stage0_job(
    sheets_client: "SheetsClient | None" = None,
) -> ProcessReport:
    """Run the Stage 0 auto-reply pipeline once.

    Responsibilities:
    a) Load config (lazy import — does not execute at import time).
    b) Determine test_mode and test_recipient from config.
    c) Create a real SheetsClient when *sheets_client* is not injected.
    d) Call process_new_leads() and return its ProcessReport.
    e) Log job start / complete with counters; never log PII.

    Arguments:
        sheets_client: injected SheetsClient for testing.  When None a
            real client is built from config and
            ensure_date_column_format() is called on it.

    Raises:
        RuntimeError: if STAGE0_TEST_MODE=1 and TEST_RECIPIENT_EMAIL is
            missing (propagated from process_new_leads).
    """
    from src.core import config  # lazy import — avoids config load during tests

    test_mode: bool = config.STAGE0_TEST_MODE
    test_recipient: str | None = config.TEST_RECIPIENT_EMAIL

    logger.info("Stage0 job start — test_mode=%s", test_mode)
    if test_mode:
        logger.info("TEST MODE active — all outbound emails go to test recipient")

    if sheets_client is None:
        from src.storage.sheets import SheetsClient as _SheetsClient
        sheets_client = _SheetsClient(
            service_account_json=config.GOOGLE_SERVICE_ACCOUNT_JSON,
            sheet_id=config.GOOGLE_SHEET_ID,
        )
        sheets_client.ensure_date_column_format()

    report = process_new_leads(
        sheets_client,
        config.CALENDAR_URL,
        smtp_host=config.SMTP_HOST,
        smtp_port=config.SMTP_PORT,
        smtp_user=config.SMTP_USER,
        smtp_password=config.SMTP_PASS,
        smtp_from_email=config.SMTP_FROM_EMAIL,
        test_mode=test_mode,
        test_recipient=test_recipient,
    )

    logger.info(
        "Stage0 job complete — scanned=%d new=%d sent=%d failed=%d",
        report.total_input_leads,
        report.new_leads_detected,
        report.emails_sent,
        report.emails_failed,
    )

    followup_updated = process_followups(sheets_client)
    logger.info("Stage0 follow-up step complete — updated=%d", followup_updated)

    return report


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    try:
        run_stage0_job()
    except Exception:
        logger.exception("Stage0 job failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
