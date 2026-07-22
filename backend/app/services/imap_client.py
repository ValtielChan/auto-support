"""Thin wrapper around imaplib for testing connections and fetching new mail."""

import email
import html as htmllib
import imaplib
import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime

# Zero-width / invisible characters marketers stuff into mail (and the combining
# grapheme joiner, &#847;) - dropped so bodies read as real text.
_INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x034F, 0x180E], None
)


def _clean_text(text: str) -> str:
    """Decode HTML entities and strip invisible junk so a body is human-readable."""
    text = htmllib.unescape(text)
    text = text.translate(_INVISIBLE)
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _connect(host: str, port: int, use_ssl: bool, username: str, password: str):
    if use_ssl:
        conn = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)
    conn.login(username, password)
    return conn


def test_connection(host, port, use_ssl, username, password, folder="INBOX") -> str:
    """Raise on failure, return a human-readable detail string on success."""
    conn = _connect(host, port, use_ssl, username, password)
    try:
        status, data = conn.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError(f"Cannot open folder {folder!r}: {data}")
        count = int(data[0])
        return f"Connected - folder {folder} contains {count} message(s)"
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _decode_str(value) -> str:
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _extract_body(msg: Message) -> str:
    """Prefer text/plain; fall back to a crude text version of text/html."""
    plain, html = None, None
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html is None:
            html = text
    if plain is not None:
        return _clean_text(plain)
    if html is not None:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return _clean_text(text)
    return ""


def _extract_html(msg: Message) -> str:
    """Return the raw text/html part of a message (decoded), or '' if none."""
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() != "text/html":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")
    return ""


def sanitize_html(html: str, limit: int = 400_000) -> str:
    """Defence-in-depth cleanup of untrusted email HTML.

    The real isolation is the sandboxed <iframe> that renders this (no allow-scripts,
    so nothing here can execute JS); this just strips the obvious dangerous bits and
    external-loading tags while KEEPING inline styles and <style> so the mail still
    looks like it should.
    """
    if not html:
        return ""
    html = html[:limit]
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<(iframe|object|embed|form|link|meta|base)\b[^>]*/?>", "", html, flags=re.I)
    html = re.sub(r"</(iframe|object|embed|form)\s*>", "", html, flags=re.I)
    # inline event handlers: on...="" / on...='' / on...=x
    html = re.sub(r"""\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", "", html, flags=re.I)
    # neutralise javascript:/vbscript: URLs in href/src
    html = re.sub(r"""(href|src)\s*=\s*(["'])\s*(?:javascript|vbscript):[^"']*\2""",
                  r'\1=\2#\2', html, flags=re.I)
    return html


def _parse_message(uid: int, msg: Message) -> dict:
    received_at = None
    if msg.get("Date"):
        try:
            received_at = parsedate_to_datetime(msg["Date"])
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
        except Exception:
            received_at = None
    from_name, from_addr = parseaddr(_decode_str(msg.get("From")))
    return {
        "imap_uid": uid,
        "message_id": (msg.get("Message-ID") or f"<no-message-id-uid-{uid}>").strip(),
        "from_address": f"{from_name} <{from_addr}>".strip() if from_name else from_addr,
        "from_email": from_addr.lower(),
        "to_address": _decode_str(msg.get("To")),
        "subject": _decode_str(msg.get("Subject")),
        "body_text": _extract_body(msg),
        "received_at": received_at or datetime.now(timezone.utc),
        "is_auto_reply": _looks_auto_generated(msg),
    }


def _looks_auto_generated(msg: Message) -> bool:
    """Detect bounces / auto-replies so the agent never answers a robot."""
    if (msg.get("Auto-Submitted") or "").lower() not in ("", "no"):
        return True
    if msg.get("X-Autoreply") or msg.get("X-Autorespond"):
        return True
    precedence = (msg.get("Precedence") or "").lower()
    return precedence in ("bulk", "auto_reply", "junk")


def _uid_set(uids) -> str:
    """Normalize one uid or a list of uids into an IMAP uid-set string ('1,2,3')."""
    if isinstance(uids, int):
        uids = [uids]
    return ",".join(str(int(u)) for u in uids)


def list_mailbox(
    host, port, use_ssl, username, password, folder, limit: int = 50
) -> list[dict]:
    """Return the most recent messages with their read/unread flag (newest first).

    Read-only: uses BODY.PEEK so listing never flips the \\Seen flag. This is the
    live mailbox view, independent of what the agent has ingested.
    """
    conn = _connect(host, port, use_ssl, username, password)
    try:
        status, data = conn.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError(f"Cannot open folder {folder!r}: {data}")
        status, data = conn.uid("search", None, "ALL")
        if status != "OK":
            raise RuntimeError(f"Search failed: {data}")
        uids = sorted(int(u) for u in (data[0].split() if data[0] else []))
        recent = uids[-limit:]
        out = []
        for uid in reversed(recent):  # newest first
            status, d = conn.uid(
                "fetch",
                str(uid),
                "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])",
            )
            if status != "OK" or not d or d[0] is None or not isinstance(d[0], tuple):
                continue
            meta = d[0][0] or b""
            seen = b"\\Seen" in meta
            hdr = email.message_from_bytes(d[0][1])
            from_name, from_addr = parseaddr(_decode_str(hdr.get("From")))
            received_at = None
            if hdr.get("Date"):
                try:
                    received_at = parsedate_to_datetime(hdr["Date"])
                    if received_at.tzinfo is None:
                        received_at = received_at.replace(tzinfo=timezone.utc)
                except Exception:
                    received_at = None
            out.append(
                {
                    "uid": uid,
                    "message_id": (hdr.get("Message-ID") or "").strip(),
                    "from_address": f"{from_name} <{from_addr}>".strip() if from_name else from_addr,
                    "subject": _decode_str(hdr.get("Subject")),
                    "received_at": received_at,
                    "seen": seen,
                }
            )
        return out
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def fetch_message(host, port, use_ssl, username, password, folder, uid: int) -> dict:
    """Fetch one full message by UID without marking it read (BODY.PEEK)."""
    conn = _connect(host, port, use_ssl, username, password)
    try:
        status, data = conn.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError(f"Cannot open folder {folder!r}: {data}")
        status, d = conn.uid("fetch", str(uid), "(FLAGS BODY.PEEK[])")
        if status != "OK" or not d or d[0] is None or not isinstance(d[0], tuple):
            raise RuntimeError(f"Message uid {uid} not found")
        seen = b"\\Seen" in (d[0][0] or b"")
        msg = email.message_from_bytes(d[0][1])
        parsed = _parse_message(uid, msg)
        parsed["seen"] = seen
        # Only the live reader needs the (heavy) rendered HTML; not stored in the DB.
        parsed["body_html"] = sanitize_html(_extract_html(msg))
        return parsed
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def set_seen(host, port, use_ssl, username, password, folder, uids, seen: bool) -> None:
    """Mark one or more messages read (seen=True) or unread on the server."""
    uid_set = _uid_set(uids)
    if not uid_set:
        return
    conn = _connect(host, port, use_ssl, username, password)
    try:
        status, data = conn.select(folder)  # read-write
        if status != "OK":
            raise RuntimeError(f"Cannot open folder {folder!r}: {data}")
        command = "+FLAGS" if seen else "-FLAGS"
        status, data = conn.uid("store", uid_set, command, "(\\Seen)")
        if status != "OK":
            raise RuntimeError(f"Could not update flags on {uid_set}: {data}")
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def delete_messages(host, port, use_ssl, username, password, folder, uids) -> None:
    """Permanently remove one or more messages from the folder (\\Deleted + expunge)."""
    uid_set = _uid_set(uids)
    if not uid_set:
        return
    conn = _connect(host, port, use_ssl, username, password)
    try:
        status, data = conn.select(folder)  # read-write
        if status != "OK":
            raise RuntimeError(f"Cannot open folder {folder!r}: {data}")
        status, data = conn.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
        if status != "OK":
            raise RuntimeError(f"Could not flag {uid_set} for deletion: {data}")
        conn.expunge()
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def fetch_new_messages(host, port, use_ssl, username, password, folder) -> list[dict]:
    """Fetch ALL unread messages, oldest first.

    Unread (\\Seen absent) is the single source of truth for "not yet handled by the
    agent": whatever is unread gets (re)processed, regardless of whether we've seen it
    before. The folder is opened readonly (BODY.PEEK) so fetching never flips \\Seen;
    the runner marks a message read only *after* it has successfully handled it, which
    is what stops it from being reprocessed on the next tick.
    """
    conn = _connect(host, port, use_ssl, username, password)
    try:
        status, data = conn.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError(f"Cannot open folder {folder!r}: {data}")
        status, data = conn.uid("search", None, "UNSEEN")
        if status != "OK":
            raise RuntimeError(f"UID search failed: {data}")
        uids = sorted(int(u) for u in (data[0].split() if data[0] else []))
        messages = []
        for uid in uids:
            status, msg_data = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            if status != "OK" or not msg_data or msg_data[0] is None or not isinstance(msg_data[0], tuple):
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            messages.append(_parse_message(uid, email.message_from_bytes(raw)))
        return messages
    finally:
        try:
            conn.logout()
        except Exception:
            pass
