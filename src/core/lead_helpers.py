"""Pure helper functions for lead processing logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")

# Human-friendly format for Google Sheets (no seconds, no timezone suffix).
_SHEET_DT_FMT = "%Y-%m-%d %H:%M"

# ---------------------------------------------------------------------------
# Morfeusz2 — lazy singleton
# ---------------------------------------------------------------------------

# The instance is created on first use, not at import time.
# This prevents a hard crash when morfeusz2 is unavailable (e.g. missing
# binary on a new deployment environment).  _morf_ready acts as a sentinel
# so that we attempt initialization only once per process.
_morf_instance: object = None
_morf_ready: bool = False


def _get_morf() -> object | None:
    """Return the shared Morfeusz instance, or None if unavailable.

    Initialised at most once per process (lazy singleton).
    Swallows ImportError and any C-extension failure so the rest of the
    module keeps working without morfeusz2 installed.
    """
    global _morf_instance, _morf_ready
    if _morf_ready:
        return _morf_instance
    _morf_ready = True
    try:
        import morfeusz2  # noqa: PLC0415
        _morf_instance = morfeusz2.Morfeusz(generate=True, analyse=False)
    except Exception:  # ImportError or C-extension init failure
        _morf_instance = None
    return _morf_instance


def to_vocative_first_name(first_name: str) -> str | None:
    """Return the Polish vocative (singular) form of *first_name* via morfeusz2.

    Returns None when:
    - morfeusz2 is not available
    - generation yields no singular vocative
    - any error occurs

    Prefers forms tagged with a dedicated ':voc:' case over compound tags
    (e.g. 'nom.gen.dat.acc.inst.loc.voc') which indicate indeclinable words.
    """
    morf = _get_morf()
    if morf is None:
        return None

    try:
        results = morf.generate(first_name)  # type: ignore[union-attr]
    except Exception:
        return None

    # Two-pass: first look for a dedicated vocative tag (e.g. "subst:sg:voc:m1"),
    # then fall back to compound tags that include 'voc'.
    fallback = None
    for result in results:
        surface, tag = result[0], result[2]
        parts = tag.split(":")
        if "sg" not in parts:
            continue
        # Check if 'voc' appears as a standalone case (not in a dot-joined group).
        case_parts = [p for p in parts if "." in p or p == "voc"]
        for cp in case_parts:
            cases = cp.split(".")
            if "voc" in cases:
                if cases == ["voc"]:
                    # Dedicated vocative — best match.
                    return surface
                if fallback is None:
                    fallback = surface
    return fallback


def generate_vocative(full_name_or_company: str) -> str:
    """Return a personalised Polish greeting if a vocative can be derived.

    Extracts the first whitespace-delimited token (assumed to be a first name
    or the leading word of a company name) and attempts to produce a Polish
    vocative via morfeusz2.

    Returns:
        "Dzień dobry, {vocative},"  when vocative is found
        "Dzień dobry,"              otherwise (unknown name, company string,
                                    empty input, or morfeusz2 unavailable)
    """
    token = full_name_or_company.strip().split()[0] if full_name_or_company.strip() else ""
    if not token:
        return "Dzień dobry,"
    vocative = to_vocative_first_name(token)
    if vocative:
        return f"Dzień dobry, {vocative},"
    return "Dzień dobry,"


# ---------------------------------------------------------------------------
# Lead-state helpers
# ---------------------------------------------------------------------------

def is_new_lead(row: dict[str, str]) -> bool:
    """A lead is new when it has an email but no auto_email_sent_at yet."""
    return bool(row.get("email", "").strip()) and not row.get("auto_email_sent_at", "").strip()


def warsaw_now_formatted() -> str:
    """Current time in Europe/Warsaw as 'YYYY-MM-DD HH:MM'."""
    return datetime.now(WARSAW_TZ).strftime(_SHEET_DT_FMT)


def followup_due_formatted(sent_at_str: str, days: int = 3) -> str:
    """Compute followup_due_at as *sent_at + days*, returned in the same format."""
    sent = datetime.strptime(sent_at_str, _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    due = sent + timedelta(days=days)
    return due.strftime(_SHEET_DT_FMT)


def is_followup_due(row: dict[str, str]) -> bool:
    """True when followup_due_at has passed and followup_required is not YES."""
    due_str = row.get("followup_due_at", "").strip()
    if not due_str:
        return False
    if row.get("followup_required", "").strip().upper() == "YES":
        return False
    try:
        due = datetime.strptime(due_str, _SHEET_DT_FMT).replace(tzinfo=WARSAW_TZ)
    except ValueError:
        return False
    return datetime.now(WARSAW_TZ) >= due
