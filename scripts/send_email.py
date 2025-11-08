#!/usr/bin/env python3
"""Send email via SMTP using env-configured credentials."""

from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage


def send_email(subject: str, body: str, to_address: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "25"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "false").lower() in {"true", "1", "yes"}
    sender = os.getenv("ALERT_EMAIL_FROM", "alerts@technical-service-assistant.local")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_address
    msg.set_content(body)

    if smtp_use_tls:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: send_email.py <subject> <body>", file=sys.stderr)
        return 1
    to_addr = os.getenv("ALERT_EMAIL_TO")
    if not to_addr:
        print("ALERT_EMAIL_TO not configured", file=sys.stderr)
        return 1
    subject = sys.argv[1]
    body = sys.argv[2]
    send_email(subject, body, to_addr)
    print("Email sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
