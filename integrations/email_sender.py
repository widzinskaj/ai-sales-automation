"""SMTP email sender — builds and sends the Stage 0 auto-reply."""

from __future__ import annotations

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from core.lead_helpers import to_vocative_first_name

logger = logging.getLogger(__name__)


def extract_first_name(full_name: str) -> str | None:
    """Return the first whitespace-delimited token, or None if empty."""
    parts = full_name.strip().split()
    return parts[0] if parts else None


# Masculine Polish first names that end with 'a' (exceptions to the
# "ends-with-a → feminine" heuristic).  Kept short and lowercase.
_MASCULINE_ENDING_A: frozenset[str] = frozenset({
    "barnaba", "bonawentura", "boryna", "jarema", "kosma",
    "kuba", "saba", "sasza",
})


def guess_gender(first_name: str) -> str | None:
    """Simple offline heuristic for Polish first names.

    Returns 'f' (feminine), 'm' (masculine), or None (uncertain).
    """
    name = first_name.strip().lower()
    if not name:
        return None
    if name in _MASCULINE_ENDING_A:
        return "m"
    if name.endswith("a"):
        return "f"
    if name[-1] in "bcdefghijklmnoprstuvwxyz":
        return "m"
    return None


def build_greeting(full_name: str | None) -> str:
    """Polish greeting with Pani/Panie honorific in vocative case.

    Returns 'Dzień dobry, Pani {wołacz},' / 'Dzień dobry, Panie {wołacz},'
    when vocative and gender can be determined, otherwise 'Dzień dobry,'.
    """
    if not full_name:
        return "Dzień dobry,"
    first = extract_first_name(full_name)
    if not first:
        return "Dzień dobry,"
    vocative = to_vocative_first_name(first)
    if not vocative:
        return "Dzień dobry,"
    gender = guess_gender(first)
    if gender == "f":
        return f"Dzień dobry, Pani {vocative},"
    if gender == "m":
        return f"Dzień dobry, Panie {vocative},"
    return "Dzień dobry,"


def _build_message(
    *,
    from_email: str,
    from_name: str,
    to_email: str,
    full_name: str,
    calendar_link: str,
    attachment_paths: list[str],
) -> MIMEMultipart:
    """Compose the auto-reply MIME message."""
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to_email
    msg["Subject"] = "Potwierdzenie otrzymania zapytania"

    greeting = build_greeting(full_name)
    body = (
        f"{greeting}\n\n"
        "Dziękujemy za przesłanie zapytania. W załączeniu przesyłamy "
        "materiały, które pomogą Państwu zapoznać się z naszą ofertą.\n\n"
        "Jeśli chcieliby Państwo umówić się na rozmowę, zapraszamy "
        "do wyboru terminu:\n"
        f"{calendar_link}\n\n"
        "Pozdrawiamy serdecznie"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path_str in attachment_paths:
        path = Path(path_str)
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")
        with open(path, "rb") as fh:
            part = MIMEApplication(fh.read(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        msg.attach(part)

    return msg


def send_auto_reply(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_email: str,
    from_name: str,
    to_email: str,
    full_name: str,
    calendar_link: str,
    attachment_paths: list[str],
) -> None:
    """Send the auto-reply email via SMTP/TLS.

    Raises on any failure so the caller can record the error.
    """
    msg = _build_message(
        from_email=from_email,
        from_name=from_name,
        to_email=to_email,
        full_name=full_name,
        calendar_link=calendar_link,
        attachment_paths=attachment_paths,
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    logger.info("Auto-reply sent to lead (email hidden)")
