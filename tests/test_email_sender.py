"""Unit tests for integrations.email_sender — no network required."""

from __future__ import annotations

from integrations.email_sender import extract_first_name, guess_gender


# ------------------------------------------------------------------
# extract_first_name
# ------------------------------------------------------------------

class TestExtractFirstName:
    def test_full_name(self):
        assert extract_first_name("Anna Kowalska") == "Anna"

    def test_single_name(self):
        assert extract_first_name("Marek") == "Marek"

    def test_multiple_parts(self):
        assert extract_first_name("Jan Maria Rokita") == "Jan"

    def test_empty_string(self):
        assert extract_first_name("") is None

    def test_whitespace_only(self):
        assert extract_first_name("   ") is None

    def test_leading_whitespace(self):
        assert extract_first_name("  Anna Kowalska") == "Anna"


# ------------------------------------------------------------------
# guess_gender
# ------------------------------------------------------------------

class TestGuessGender:
    def test_feminine_ending_a(self):
        assert guess_gender("Anna") == "f"
        assert guess_gender("Katarzyna") == "f"
        assert guess_gender("Monika") == "f"

    def test_masculine_no_a(self):
        assert guess_gender("Marek") == "m"
        assert guess_gender("Tomasz") == "m"
        assert guess_gender("Piotr") == "m"

    def test_masculine_exception_ending_a(self):
        assert guess_gender("Kuba") == "m"
        assert guess_gender("Barnaba") == "m"
        assert guess_gender("Bonawentura") == "m"

    def test_case_insensitive(self):
        assert guess_gender("KUBA") == "m"
        assert guess_gender("ANNA") == "f"

    def test_empty(self):
        assert guess_gender("") is None
        assert guess_gender("  ") is None
