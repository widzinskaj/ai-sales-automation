"""Google Sheets integration — read/write lead rows by column name."""

from __future__ import annotations

import logging
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# System-managed columns — only these are written by the application.
SYSTEM_COLUMNS = (
    "auto_email_sent_at",
    "auto_email_status",
    "followup_due_at",
    "followup_required",
)


class SheetsClient:
    """Thin wrapper around gspread for column-name-based access."""

    def __init__(self, service_account_json: str, sheet_id: str, tab_name: str) -> None:
        creds = Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        self._ws = spreadsheet.worksheet(tab_name)
        self._headers: list[str] = self._ws.row_values(1)
        logger.info(
            "Connected to sheet '%s' tab '%s' (%d columns)",
            sheet_id[:8] + "...",
            tab_name,
            len(self._headers),
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all_rows(self) -> list[dict[str, str]]:
        """Return every data row as a dict keyed by header name."""
        records = self._ws.get_all_records(head=1, default_blank="")
        # Ensure every value is a string for uniform handling.
        return [{k: str(v) for k, v in row.items()} for row in records]

    # ------------------------------------------------------------------
    # Write (only system columns)
    # ------------------------------------------------------------------

    def update_row(self, row_number: int, updates: dict[str, str]) -> None:
        """Write *updates* into the given 1-based row (header = row 1).

        Only columns listed in SYSTEM_COLUMNS are allowed.
        """
        for col_name in updates:
            if col_name not in SYSTEM_COLUMNS:
                raise ValueError(f"Refusing to write non-system column: {col_name}")

        cells: list[gspread.Cell] = []
        for col_name, value in updates.items():
            col_index = self._col_index(col_name)
            cells.append(gspread.Cell(row=row_number, col=col_index, value=value))

        if cells:
            self._ws.update_cells(cells)
            logger.info("Updated row %d: %s", row_number, list(updates.keys()))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _col_index(self, col_name: str) -> int:
        """Return 1-based column index for *col_name*."""
        try:
            return self._headers.index(col_name) + 1
        except ValueError:
            raise KeyError(f"Column '{col_name}' not found in sheet headers: {self._headers}")
