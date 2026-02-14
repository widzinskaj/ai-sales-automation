"""Google Sheets integration — read/write lead rows by column name."""

from __future__ import annotations
from core.config import GOOGLE_SHEET_TAB_INPUT, GOOGLE_SHEET_TAB_STATUS

INPUT_HEADERS = [...]
INPUT_HEADERS = [...]
INPUT_HEADERS = [...]

STATUS_HEADERS = [...]
STATUS_HEADERS = [...]
STATUS_HEADERS = [...]
STATUS_HEADERS = [...]
STATUS_HEADERS = [...]
STATUS_HEADERS = [...]



import logging
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# System-managed columns — only these are written by the application.
SYSTEM_COLUMNS = frozenset({
    "auto_email_sent_at",
    "auto_email_status",
    "followup_due_at",
    "followup_required",
})

# Columns that hold datetime values and should be formatted in the sheet.
DATE_COLUMNS = ("auto_email_sent_at", "followup_due_at")

# Google Sheets number format pattern for datetime columns.
_DATE_NUMBER_FORMAT = {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm"}


class SheetsClient:
    """Thin wrapper around gspread for column-name-based access."""

    def __init__(self, service_account_json: str, sheet_id: str) -> None:
        creds = Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
        gc = gspread.authorize(creds)
        self._spreadsheet = gc.open_by_key(sheet_id)
        self._ws_input = self._spreadsheet.worksheet(GOOGLE_SHEET_TAB_INPUT)
        self._ws_status = self._spreadsheet.worksheet(GOOGLE_SHEET_TAB_STATUS)
        self._headers_input: list[str] = self._ws_input.row_values(1)
        self._headers_status: list[str] = self._ws_status.row_values(1)

        logger.info(
            "Connected to sheet '%s' tabs input='%s' (%d cols), status='%s' (%d cols)",
            sheet_id[:8] + "...",
            GOOGLE_SHEET_TAB_INPUT,
            len(self._headers_input),
            GOOGLE_SHEET_TAB_STATUS,
            len(self._headers_status),
)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all_rows(self) -> list[dict[str, str]]:
        """Return every data row as a dict keyed by header name."""
        records = self._ws_status.get_all_records(head=1, default_blank="")
        return [{k: str(v) for k, v in row.items()} for row in records]

    # ------------------------------------------------------------------
    # Write (only system columns, USER_ENTERED)
    # ------------------------------------------------------------------

    def update_row(self, row_number: int, updates: dict[str, str]) -> None:
        """Write *updates* into the given 1-based row (header = row 1).

        Only columns listed in SYSTEM_COLUMNS are allowed.
        Uses valueInputOption=USER_ENTERED so Sheets parses dates natively.
        """
        for col_name in updates:
            if col_name not in SYSTEM_COLUMNS:
                raise ValueError(f"Refusing to write non-system column: {col_name}")

        for col_name, value in updates.items():
            col_index = self._col_index(col_name)
            cell_label = gspread.utils.rowcol_to_a1(row_number, col_index)
            self._ws_status.update(
                cell_label,
                [[value]],
                value_input_option="USER_ENTERED",
            )

        logger.info("Updated row %d: %s", row_number, list(updates.keys()))

    # ------------------------------------------------------------------
    # Date column formatting (idempotent)
    # ------------------------------------------------------------------

    def ensure_date_column_format(self) -> None:
        """Apply yyyy-mm-dd hh:mm number format to date columns.

        Uses the Sheets API batchUpdate / repeatCell request.
        Safe to call multiple times — the format is simply overwritten.
        """
        sheet_id = self._ws_status.id
        requests: list[dict[str, Any]] = []

        for col_name in DATE_COLUMNS:
            try:
                col_index = self._col_index(col_name) - 1  # 0-based for API
            except KeyError:
                logger.warning("Date column '%s' not found in headers, skipping format", col_name)
                continue

            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,       # skip header
                        "startColumnIndex": col_index,
                        "endColumnIndex": col_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": _DATE_NUMBER_FORMAT,
                        },
                    },
                    "fields": "userEnteredFormat.numberFormat",
                },
            })

        if requests:
            self._spreadsheet.batch_update({"requests": requests})
            logger.info("Date column format applied to: %s", list(DATE_COLUMNS))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _col_index(self, col_name: str) -> int:
        """Return 1-based column index for *col_name*."""
        try:
            return self._headers_status.index(col_name) + 1
        except ValueError:
            raise KeyError(f"Column '{col_name}' not found in sheet headers: {self._headers_status}")
