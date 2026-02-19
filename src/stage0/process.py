"""Stage 0 — build email drafts for new leads (no SMTP, no status writes)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.email.attachments_stage0 import get_stage0_attachments_from_env
from src.email.template_stage0 import build_stage0_email
from src.storage.sheets import SheetsClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessReport:
    total_input_leads: int
    new_leads_detected: int
    drafts_built: int


def process_new_leads(
    sheets_client: SheetsClient,
    calendar_url: str,
) -> ProcessReport:
    """Sync status rows and build email drafts for all new leads.

    Side effects:
    - calls ensure_status_rows_exist() (structural sync, idempotent)
    - logs one line per draft built
    No SMTP. No auto_email_sent_at / auto_email_status writes.
    """
    sheets_client.ensure_status_rows_exist()

    input_rows = sheets_client.read_input_rows()
    new_leads = sheets_client.get_new_leads()

    attachments: list[Path] = get_stage0_attachments_from_env()

    drafts_built = 0
    for lead in new_leads:
        email = lead.get("Email", "").strip().lower()
        if not email:
            logger.warning("Skipping lead with missing email: %r", lead)
            continue

        try:
            draft = build_stage0_email(
                calendar_url=calendar_url,
                attachments=attachments,
            )
        except Exception:
            logger.exception("Failed to build draft for email=%s — skipping", email)
            continue

        logger.info("Draft built: email=%s subject=%r", email, draft.subject)
        drafts_built += 1

    logger.info(
        "process_new_leads done — input=%d new=%d drafts=%d",
        len(input_rows),
        len(new_leads),
        drafts_built,
    )

    return ProcessReport(
        total_input_leads=len(input_rows),
        new_leads_detected=len(new_leads),
        drafts_built=drafts_built,
    )
