"""Google Sheets integration — read/write lead rows by column name."""

from __future__ import annotations
from core.config import GOOGLE_SHEET_TAB_INPUT, GOOGLE_SHEET_TAB_STATUS

INPUT_HEADERS = [
    "Imię i nazwisko / Firma",
    "Email",
    "Telefon dodatkowy",
]

STATUS_HEADERS = [
    "email",
    "auto_email_sent_at",
    "auto_email_status",
    "followup_due_at",
    "followup_required",
    "followup_completed_at",
]


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

    def read_input_rows(self) -> list[dict[str, str]]:
        """Return all non-empty input rows with normalized email."""
        records = self._ws_input.get_all_records(head=1, default_blank="")

        cleaned_rows: list[dict[str, str]] = []

        for row in records:
            email = str(row.get("Email", "")).strip().lower()

            if not email:
                continue  # skip empty rows

            row["Email"] = email
            cleaned_rows.append({k: str(v) for k, v in row.items()})

        return cleaned_rows


    def get_all_rows(self) -> list[dict[str, str]]:
        """Return every data row as a dict keyed by header name."""
        records = self._ws_status.get_all_records(head=1, default_blank="")
        return [{k: str(v) for k, v in row.items()} for row in records]
    
    def read_status_rows(self) -> list[dict[str, str]]:
        """Return every status row as a dict keyed by header name."""
        records = self._ws_status.get_all_records(head=1, default_blank="")
        return [{k: str(v) for k, v in row.items()} for row in records]


    def get_status_index_by_email(self) -> dict[str, dict[str, str]]:
        """Map: email -> status row dict (email normalized)."""
        rows = self.read_status_rows()
        mapping: dict[str, dict[str, str]] = {}

        for row in rows:
            email = str(row.get("email", "")).strip().lower()
            if not email:
                continue
            mapping[email] = row

        return mapping

    def get_new_leads(self) -> list[dict[str, str]]:
        """Return input rows that are new or not yet emailed (idempotent)."""
        input_rows = self.read_input_rows()
        status_index = self.get_status_index_by_email()

        new_rows: list[dict[str, str]] = []
        for row in input_rows:
            email = str(row.get("Email", "")).strip().lower()
            if not email:
                continue

            status_row = status_index.get(email)
            sent_at = "" if not status_row else str(status_row.get("auto_email_sent_at", "")).strip()

            # new = missing in status OR not sent yet
            if (status_row is None) or (sent_at == ""):
                new_rows.append(row)

        return new_rows

    def ensure_status_rows_exist(self) -> None:
        """Ensure every input email has a row in status sheet."""
        input_rows = self.read_input_rows()
        status_index = self.get_status_index_by_email()

        for row in input_rows:
            email = str(row.get("Email", "")).strip().lower()
            if not email:
                continue

            if email not in status_index:
                # append new status row
                self._ws_status.append_row(
                    [
                        email,  # email
                        "",     # auto_email_sent_at
                        "",     # auto_email_status
                        "",     # followup_due_at
                        "",     # followup_required
                        "",     # followup_completed_at
                    ],
                    value_input_option="USER_ENTERED",
                )

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
            
    def _validate_headers(self, actual: list[str], expected: list[str], tab_name: str) -> None:
        actual_clean = [h.strip() for h in actual if h is not None]
        expected_clean = [h.strip() for h in expected]

        if actual_clean != expected_clean:
            raise RuntimeError(
                f"Invalid headers in tab '{tab_name}'. "
                f"Expected: {expected_clean}. Got: {actual_clean}."
            )

