"""Thin wrapper around smtplib for testing connections and sending mail."""

import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid


def _header(value: str) -> str:
    """Collapse CR/LF and runs of whitespace so header values are injection-safe.

    Original subjects/addresses pulled from IMAP can contain raw newlines, which
    the email lib rejects ("Header values may not contain linefeed or carriage
    return characters") — that aborts the reply/escalation for that mail.
    """
    return re.sub(r"\s+", " ", (value or "").replace("\r", " ").replace("\n", " ")).strip()


def _connect(host: str, port: int, use_tls: bool, username: str, password: str):
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
    if username:
        server.login(username, password)
    return server


def test_connection(host, port, use_tls, username, password) -> str:
    server = _connect(host, port, use_tls, username, password)
    try:
        server.noop()
        return "Connected and authenticated"
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_email(
    host,
    port,
    use_tls,
    username,
    password,
    from_name: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    html: str | None = None,
) -> str:
    """Send an email (plain-text, plus an HTML alternative when given); returns Message-ID."""
    msg = EmailMessage()
    msg["From"] = formataddr((_header(from_name), from_addr)) if from_name else from_addr
    msg["To"] = _header(to_addr)
    msg["Subject"] = _header(subject)
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = _header(in_reply_to)
        msg["References"] = _header(in_reply_to)
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    server = _connect(host, port, use_tls, username, password)
    try:
        server.send_message(msg)
        return msg["Message-ID"]
    finally:
        try:
            server.quit()
        except Exception:
            pass
