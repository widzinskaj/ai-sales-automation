"""Tests for process_followups() and job-level follow-up integration.

Scenarios covered:
    TestProcessFollowups
        a) update_row called with correct patch when followup fields change
        b) update_row NOT called when nothing changes
        c) row with empty email is skipped
        d) row where get_status_row_number_by_email returns None is skipped
        e) only changed fields included in patch (partial update)
        f) followup_required set to NO when followup_completed_at is set

    TestJobFollowupRegression
        - run_stage0_job calls process_followups (regression guard)
        - update_row is invoked for a row that needs follow-up scheduling
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.core.config as _cfg
from src.stage0.job import run_stage0_job
from src.stage0.process import process_followups

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SENT_AT = "2025-03-10 09:15"
DUE_AT = "2025-03-13 09:15"  # SENT_AT + 3 days


def _row(**overrides) -> dict:
    base = {
        "email": "lead@example.com",
        "auto_email_sent_at": SENT_AT,
        "auto_email_status": "SENT",
        "followup_due_at": "",
        "followup_required": "",
        "followup_completed_at": "",
    }
    base.update(overrides)
    return base


class FakeSheetsClient:
    """Minimal in-memory SheetsClient for process_followups tests."""

    def __init__(
        self,
        rows: list[dict],
        row_numbers: dict[str, int],
    ) -> None:
        self._rows = rows
        self._row_numbers = row_numbers
        self.update_calls: list[tuple[int, dict]] = []

    def read_status_rows(self) -> list[dict]:
        return list(self._rows)

    def get_status_row_number_by_email(self, email: str) -> int | None:
        return self._row_numbers.get(email.strip().lower())

    def update_row(self, row_number: int, updates: dict) -> None:
        self.update_calls.append((row_number, updates))


# ---------------------------------------------------------------------------
# TestProcessFollowups — unit tests for the pure orchestration function
# ---------------------------------------------------------------------------

class TestProcessFollowups:

    def test_update_called_with_correct_patch_when_fields_change(self):
        """New lead with sent_at and no due_at → followup_due_at + followup_required written."""
        client = FakeSheetsClient([_row()], {"lead@example.com": 2})

        updated = process_followups(client)

        assert updated == 1
        assert len(client.update_calls) == 1
        row_num, patch = client.update_calls[0]
        assert row_num == 2
        assert patch == {"followup_due_at": DUE_AT, "followup_required": "YES"}

    def test_update_not_called_when_nothing_changes(self):
        """Lead already has due_at and followup_required=YES → no write."""
        client = FakeSheetsClient(
            [_row(followup_due_at=DUE_AT, followup_required="YES")],
            {"lead@example.com": 2},
        )

        updated = process_followups(client)

        assert updated == 0
        assert client.update_calls == []

    def test_row_with_empty_email_is_skipped(self):
        row = _row(email="")
        client = FakeSheetsClient([row], {})

        updated = process_followups(client)

        assert updated == 0
        assert client.update_calls == []

    def test_row_number_none_skips_update(self):
        """If get_status_row_number_by_email returns None the row is silently skipped."""
        client = FakeSheetsClient([_row()], {})  # empty row_numbers → always None

        updated = process_followups(client)

        assert updated == 0
        assert client.update_calls == []

    def test_only_changed_fields_in_patch(self):
        """When followup_required is already YES only followup_due_at should appear in patch.

        (Edge case: due_at missing but required already set — apply_followup_logic
        will set due_at + required=YES, but required is already YES so only due_at changes.)
        """
        client = FakeSheetsClient(
            [_row(followup_due_at="", followup_required="YES")],
            {"lead@example.com": 2},
        )

        updated = process_followups(client)

        assert updated == 1
        _, patch = client.update_calls[0]
        assert "followup_due_at" in patch
        assert patch.get("followup_required") is None  # unchanged → not in patch

    def test_followup_required_set_to_no_when_completed(self):
        """Lead with followup_completed_at set → followup_required flipped to NO."""
        client = FakeSheetsClient(
            [_row(
                followup_due_at=DUE_AT,
                followup_required="YES",
                followup_completed_at="2025-03-14 10:00",
            )],
            {"lead@example.com": 2},
        )

        updated = process_followups(client)

        assert updated == 1
        _, patch = client.update_calls[0]
        assert patch == {"followup_required": "NO"}

    def test_no_sent_at_row_not_updated(self):
        """Lead without sent_at is untouched by follow-up logic."""
        client = FakeSheetsClient(
            [_row(auto_email_sent_at="", auto_email_status="")],
            {"lead@example.com": 2},
        )

        updated = process_followups(client)

        assert updated == 0
        assert client.update_calls == []

    def test_multiple_rows_independent(self):
        """Two rows: one needs update, one is already complete → only one write."""
        rows = [
            _row(email="new@example.com"),
            _row(
                email="done@example.com",
                followup_due_at=DUE_AT,
                followup_required="YES",
            ),
        ]
        client = FakeSheetsClient(
            rows,
            {"new@example.com": 2, "done@example.com": 3},
        )

        updated = process_followups(client)

        assert updated == 1
        assert len(client.update_calls) == 1
        row_num, patch = client.update_calls[0]
        assert row_num == 2
        assert patch["followup_due_at"] == DUE_AT


# ---------------------------------------------------------------------------
# TestJobFollowupRegression — verify run_stage0_job calls process_followups
# ---------------------------------------------------------------------------

FAKE_ATTACHMENTS = [Path("a.pdf"), Path("b.pdf"), Path("c.pdf")]


class TestJobFollowupRegression:
    """Guard against regressions where job runs without the follow-up step."""

    def _make_sheets_client(self, status_rows: list[dict]) -> MagicMock:
        client = MagicMock()
        client.get_new_leads.return_value = []
        client.read_input_rows.return_value = []
        client.read_status_rows.return_value = status_rows
        client.get_status_row_number_by_email.return_value = 2
        return client

    @patch.object(_cfg, "STAGE0_TEST_MODE", False)
    @patch.object(_cfg, "TEST_RECIPIENT_EMAIL", None)
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    def test_job_calls_process_followups(self, _mock_attach):
        """run_stage0_job must invoke process_followups — if it doesn't, update_row
        will not be called for a row that needs follow-up scheduling."""
        pending_row = _row()
        client = self._make_sheets_client([pending_row])

        run_stage0_job(sheets_client=client)

        client.read_status_rows.assert_called_once()

    @patch.object(_cfg, "STAGE0_TEST_MODE", False)
    @patch.object(_cfg, "TEST_RECIPIENT_EMAIL", None)
    @patch("src.stage0.process.get_stage0_attachments_from_env", return_value=FAKE_ATTACHMENTS)
    def test_job_triggers_update_row_for_pending_followup(self, _mock_attach):
        """update_row must be called with follow-up patch when a row is due for scheduling."""
        pending_row = _row()
        client = self._make_sheets_client([pending_row])

        run_stage0_job(sheets_client=client)

        # At least one update_row call must carry follow-up fields
        followup_calls = [
            call for call in client.update_row.call_args_list
            if "followup_due_at" in call.args[1] or "followup_required" in call.args[1]
        ]
        assert followup_calls, (
            "run_stage0_job did not write any follow-up fields — "
            "process_followups was likely not called"
        )
        _, patch = followup_calls[0].args
        assert patch["followup_due_at"] == DUE_AT
        assert patch["followup_required"] == "YES"
