"""Stage 0 — mark leads that need follow-up (3+ days since auto-reply).

No email is sent. The flag is informational for human review.

Usage:
    python -m workflows.stage0.mark_followups
"""

from __future__ import annotations

import logging
import sys

from core import config
from core.lead_helpers import is_followup_due
from storage.sheets import SheetsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("mark_followups: starting (env=%s)", config.APP_ENV)

    sheets = SheetsClient(
        service_account_json=config.GOOGLE_SERVICE_ACCOUNT_JSON,
        sheet_id=config.GOOGLE_SHEET_ID,
        tab_name=config.GOOGLE_SHEET_TAB,
    )

    rows = sheets.get_all_rows()
    marked = 0

    for idx, row in enumerate(rows):
        row_number = idx + 2

        if not is_followup_due(row):
            continue

        lead_id = row.get("lead_id", "?")
        logger.info("Marking follow-up for lead_id=%s (row %d)", lead_id, row_number)
        sheets.update_row(row_number, {"followup_required": "YES"})
        marked += 1

    logger.info("mark_followups: done — %d lead(s) marked", marked)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("mark_followups failed")
        sys.exit(1)
