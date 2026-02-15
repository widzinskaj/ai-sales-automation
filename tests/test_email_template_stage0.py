from pathlib import Path

import pytest

from src.email.template_stage0 import build_stage0_email
from src.email.attachments_stage0 import get_stage0_attachments_from_env


DUMMY_ATTACHMENTS = [Path("a"), Path("b"), Path("c")]
CALENDAR_URL = "https://calendly.com/flexihome/konsultacja"


class TestBuildStage0Email:
    def test_build_email_contains_required_sections(self):
        draft = build_stage0_email(
            calendar_url=CALENDAR_URL,
            attachments=DUMMY_ATTACHMENTS,
        )
        assert "W załączeniu przesyłam 3 oferty" in draft.body
        assert 'standard\u201e \u201epod klucz\u201d (bez mebli ruchomych)' or \
               '\u201epod klucz\u201d (bez mebli ruchomych)' in draft.body
        for keyword in ("dyfuzja", "materiały", "akustyka", "wilgotności", "bezwładność cieplna"):
            assert keyword in draft.body, f"Missing keyword: {keyword}"

    def test_build_email_includes_calendar_url(self):
        draft = build_stage0_email(
            calendar_url=CALENDAR_URL,
            attachments=DUMMY_ATTACHMENTS,
        )
        assert CALENDAR_URL in draft.body

    def test_build_email_requires_exactly_3_attachments(self):
        with pytest.raises(ValueError):
            build_stage0_email(
                calendar_url=CALENDAR_URL,
                attachments=[Path("a"), Path("b")],
            )
        with pytest.raises(ValueError):
            build_stage0_email(
                calendar_url=CALENDAR_URL,
                attachments=[Path("a"), Path("b"), Path("c"), Path("d")],
            )

    def test_build_email_raises_on_empty_calendar_url(self):
        with pytest.raises(ValueError):
            build_stage0_email(
                calendar_url="",
                attachments=DUMMY_ATTACHMENTS,
            )


class TestGetStage0AttachmentsFromEnv:
    def test_happy_path(self, tmp_path, monkeypatch):
        files = []
        for i in range(1, 4):
            f = tmp_path / f"offer_{i}.pdf"
            f.write_bytes(b"%PDF-fake")
            files.append(f)
            monkeypatch.setenv(f"STAGE0_PDF_{i}", str(f))

        result = get_stage0_attachments_from_env()
        assert len(result) == 3
        assert result == files

    def test_missing_env(self, tmp_path, monkeypatch):
        for i in range(1, 3):
            f = tmp_path / f"offer_{i}.pdf"
            f.write_bytes(b"%PDF-fake")
            monkeypatch.setenv(f"STAGE0_PDF_{i}", str(f))
        monkeypatch.delenv("STAGE0_PDF_3", raising=False)

        with pytest.raises(ValueError, match="STAGE0_PDF_3"):
            get_stage0_attachments_from_env()

    def test_missing_file(self, tmp_path, monkeypatch):
        for i in range(1, 3):
            f = tmp_path / f"offer_{i}.pdf"
            f.write_bytes(b"%PDF-fake")
            monkeypatch.setenv(f"STAGE0_PDF_{i}", str(f))
        monkeypatch.setenv("STAGE0_PDF_3", str(tmp_path / "nonexistent.pdf"))

        with pytest.raises(ValueError, match="File not found"):
            get_stage0_attachments_from_env()
