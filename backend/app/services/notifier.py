"""Email notifier. Falls back to stdout logging when SMTP is not configured."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Email:
    to: list[str]
    subject: str
    body: str


def send_email(email: Email) -> bool:
    """Best-effort send. Returns True on success, False on failure.

    Never raises — the caller should not break the workflow on email failure.
    """
    settings = get_settings()

    if not email.to:
        logger.debug("notifier: no recipients, skipping")
        return True

    if not settings.SMTP_HOST:
        logger.info(
            "notifier(stdout): to=%s subject=%s\n%s",
            email.to,
            email.subject,
            email.body,
        )
        return True

    msg = EmailMessage()
    msg["Subject"] = email.subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(email.to)
    msg.set_content(email.body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as s:
            if settings.SMTP_USE_TLS:
                s.starttls()
            if settings.SMTP_USERNAME:
                s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("notifier: send failed to=%s err=%s", email.to, exc)
        return False


def broadcast(recipients: Iterable[str], subject: str, body: str) -> None:
    to = [r for r in recipients if r]
    if not to:
        return
    send_email(Email(to=to, subject=subject, body=body))
