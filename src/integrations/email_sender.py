"""SMTP email sender — sends an EmailDraft via SMTP/STARTTLS."""

from __future__ import annotations

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.email.template_stage0 import EmailDraft

logger = logging.getLogger(__name__)


def send_email_draft(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_email: str,
    to_email: str,
    draft: EmailDraft,
) -> None:
    """Send *draft* to *to_email* via SMTP with STARTTLS.

    Raises on any failure so the caller can record the error.
    """
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = draft.subject
    msg.attach(MIMEText(draft.body, "plain", "utf-8"))

    for path in draft.attachments:
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")
        with open(path, "rb") as fh:
            part = MIMEApplication(fh.read(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)

    logger.info("Email sent to=%s subject=%r", to_email, draft.subject)
