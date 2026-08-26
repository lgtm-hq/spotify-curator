"""Optional email notifications for scheduled jobs."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import yaml

from app.config import DEFAULT_CONFIG_FILE

logger = logging.getLogger(__name__)


def _smtp_config() -> dict[str, object]:
    try:
        with DEFAULT_CONFIG_FILE.open() as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    smtp = data.get("smtp") or {}
    return smtp if isinstance(smtp, dict) else {}


def send_advisor_digest_email(
    *,
    to_address: str,
    summary: str,
    suggestion_count: int,
) -> bool:
    """Send advisor digest email when SMTP is configured."""
    smtp = _smtp_config()
    if not smtp.get("enabled"):
        logger.info(
            "Advisor digest ready for %s (%s suggestions). "
            "SMTP disabled — see in-app history.",
            to_address,
            suggestion_count,
        )
        return False

    host = str(smtp.get("host") or "")
    port = int(str(smtp.get("port") or 587))
    username = str(smtp.get("username") or "")
    password = str(smtp.get("password") or "")
    from_address = str(smtp.get("from_address") or username)
    use_tls = bool(smtp.get("use_tls", True))

    if not host or not from_address:
        logger.warning("SMTP enabled but host/from_address missing")
        return False

    message = EmailMessage()
    message["Subject"] = "Spotify Curator — AI Advisor weekly summary"
    message["From"] = from_address
    message["To"] = to_address
    message.set_content(
        "\n".join(
            [
                "Your scheduled AI Cleanup Advisor run finished.",
                "",
                summary,
                "",
                f"Suggestions: {suggestion_count}",
                "",
                "Open Spotify Curator → AI Advisor for details and to apply fixes.",
            ],
        ),
    )

    try:
        with smtplib.SMTP(host, port, timeout=20) as client:
            if use_tls:
                client.starttls()
            if username and password:
                client.login(username, password)
            client.send_message(message)
        logger.info("Sent advisor digest email to %s", to_address)
        return True
    except Exception:
        logger.exception("Failed to send advisor digest email to %s", to_address)
        return False
