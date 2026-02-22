"""Test-mode guard — prevents outbound emails from reaching real recipients.

Pure functions only.  No I/O, no side effects.
"""

from __future__ import annotations


def resolve_recipient_email(
    lead_email: str,
    *,
    test_mode: bool,
    test_recipient: str | None,
) -> str:
    """Return the actual address the outbound email should be sent to.

    In test mode (``test_mode=True``):
      - *test_recipient* must be set and non-empty; raises ``RuntimeError``
        with a clear message otherwise.
      - Returns ``test_recipient`` (stripped and lower-cased), regardless of
        ``lead_email``.  This is the hard guard that makes it structurally
        impossible to deliver to a real lead while test mode is active.

    In normal mode (``test_mode=False``):
      - Returns ``lead_email`` unchanged.
    """
    if test_mode:
        if not test_recipient or not test_recipient.strip():
            raise RuntimeError(
                "TEST_RECIPIENT_EMAIL is required when STAGE0_TEST_MODE=1. "
                "Set it to an internal address before running in test mode."
            )
        return test_recipient.strip().lower()
    return lead_email
