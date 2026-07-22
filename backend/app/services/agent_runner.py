"""The support agent pipeline: fetch new mail, classify, reply / escalate / queue."""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Agent, Email, Mailbox, Reply, RunLog
from . import crypto, imap_client, llm, smtp_client

logger = logging.getLogger("autosupport.runner")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _send_from_mailbox(mailbox: Mailbox, to_addr: str, subject: str, body: str,
                       in_reply_to: str | None = None) -> str:
    return smtp_client.send_email(
        host=mailbox.smtp_host,
        port=mailbox.smtp_port,
        use_tls=mailbox.smtp_tls,
        username=mailbox.smtp_username,
        password=crypto.decrypt(mailbox.smtp_password_enc),
        from_name=mailbox.name,
        from_addr=mailbox.email_address,
        to_addr=to_addr,
        subject=subject,
        body=body,
        in_reply_to=in_reply_to,
    )


def _reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _mark_read(mailbox: Mailbox, uids: list[int]) -> None:
    """Mark handled messages read on the server (best-effort; never fails the run)."""
    if not uids:
        return
    try:
        imap_client.set_seen(
            host=mailbox.imap_host,
            port=mailbox.imap_port,
            use_ssl=mailbox.imap_ssl,
            username=mailbox.imap_username,
            password=crypto.decrypt(mailbox.imap_password_enc),
            folder=mailbox.imap_folder,
            uids=uids,
            seen=True,
        )
    except Exception:
        logger.exception("Could not mark %d message(s) read", len(uids))


def send_reply(db: Session, reply: Reply) -> None:
    """Send a stored reply (used both by auto-send and by manual approval)."""
    email = reply.email
    mailbox = email.mailbox
    _send_from_mailbox(
        mailbox,
        to_addr=email.from_address,
        subject=_reply_subject(email.subject),
        body=reply.body,
        in_reply_to=email.message_id or None,
    )
    reply.status = "sent"
    reply.sent_at = _utcnow()
    email.status = "replied"
    db.commit()


def _fetch_into_db(db: Session, mailbox: Mailbox) -> list[Email]:
    """Pull every unread message into the emails table for (re)processing.

    Unread is the source of truth: a message already in the DB but still unread is
    re-queued (status back to `new`, prior classification cleared, stale unsent drafts
    dropped) so the agent handles it again. The DB row is kept as the running history.
    Returns the rows to consider this run (their imap_uid is refreshed to the current
    one so the runner can mark them read afterwards).
    """
    messages = imap_client.fetch_new_messages(
        host=mailbox.imap_host,
        port=mailbox.imap_port,
        use_ssl=mailbox.imap_ssl,
        username=mailbox.imap_username,
        password=crypto.decrypt(mailbox.imap_password_enc),
        folder=mailbox.imap_folder,
    )
    fetched: list[Email] = []
    seen_ids: set[str] = set()
    own_address = mailbox.email_address.lower()
    for m in messages:
        mailbox.last_seen_uid = max(mailbox.last_seen_uid, m["imap_uid"])
        message_id = m["message_id"]
        # The same Message-ID can appear under several UIDs in one fetch — handle it once.
        if message_id in seen_ids:
            continue
        seen_ids.add(message_id)
        skip = m["is_auto_reply"] or m["from_email"] == own_address

        existing = (
            db.query(Email)
            .filter(Email.mailbox_id == mailbox.id, Email.message_id == message_id)
            .first()
        )
        if existing is not None:
            # Still unread → re-queue for reprocessing. Drop stale unsent drafts so we
            # don't stack a second draft; sent replies stay as history.
            existing.imap_uid = m["imap_uid"]
            for reply in list(existing.replies):
                if reply.status == "draft":
                    db.delete(reply)
            existing.error = None
            existing.action_reason = None
            if skip:
                existing.status = "ignored"
                existing.category = "other"
                existing.category_reason = "Auto-generated message or sent by this mailbox itself"
                existing.processed_at = _utcnow()
            else:
                existing.status = "new"
                existing.category = None
                existing.category_reason = None
                existing.processed_at = None
            fetched.append(existing)
            continue

        email = Email(
            mailbox_id=mailbox.id,
            imap_uid=m["imap_uid"],
            message_id=message_id,
            from_address=m["from_address"],
            to_address=m["to_address"],
            subject=m["subject"],
            body_text=m["body_text"],
            received_at=m["received_at"],
            status="ignored" if skip else "new",
            category="other" if skip else None,
            category_reason="Auto-generated message or sent by this mailbox itself"
            if skip
            else None,
            processed_at=_utcnow() if skip else None,
        )
        db.add(email)
        fetched.append(email)
    db.commit()
    return fetched


def _build_report(emails) -> str:
    """Serialize a per-email outcome report (what happened + why) for a run."""
    items = [
        {
            "email_id": e.id,
            "from_address": e.from_address,
            "subject": e.subject,
            "category": e.category,
            "status": e.status,
            "reason": e.error if e.status == "error" else (e.action_reason or e.category_reason),
        }
        for e in sorted(emails, key=lambda e: e.imap_uid)
    ]
    return json.dumps(items, ensure_ascii=False)


def _process_email(db: Session, mailbox: Mailbox, agent: Agent, client, model: str,
                   email: Email, run: RunLog) -> None:
    classification = llm.classify_email(client, model, agent, email)
    email.category = classification["category"]
    email.category_reason = classification["reason"]
    email.processed_at = _utcnow()

    # Spam is never engaged. Everything else goes through the reply step, which —
    # guided by the agent's playbooks & guidelines — decides reply / escalate /
    # ignore (so e.g. a marketing offer can be politely declined if configured).
    if email.category == "spam":
        email.status = "ignored"
        email.action_reason = "Classified as spam — the agent never engages spam."
        return

    allow_escalation = bool(agent.escalation_enabled and agent.escalation_email)
    result = llm.generate_reply(
        client, model, agent, agent.documents, email, email.category, allow_escalation
    )
    email.action_reason = result.get("reason") or None

    if result["action"] == "ignore":
        email.status = "ignored"
        return

    if result["action"] == "escalate":
        forward_body = (
            f"The support agent for {mailbox.name} <{mailbox.email_address}> escalated "
            f"this email.\n\nReason: {result['reason']}\n\n"
            f"--- Original message ---\n"
            f"From: {email.from_address}\n"
            f"Subject: {email.subject}\n"
            f"Date: {email.received_at}\n\n"
            f"{email.body_text}"
        )
        _send_from_mailbox(
            mailbox,
            to_addr=agent.escalation_email,
            subject=f"[Escalated] {email.subject}",
            body=forward_body,
        )
        if agent.notify_customer_on_escalation:
            _send_from_mailbox(
                mailbox,
                to_addr=email.from_address,
                subject=_reply_subject(email.subject),
                body=result["body"],
                in_reply_to=email.message_id or None,
            )
        email.status = "escalated"
        run.escalated += 1
        return

    reply = Reply(email_id=email.id, body=result["body"], status="draft", model_used=model)
    db.add(reply)
    if agent.auto_send:
        db.flush()
        send_reply(db, reply)
        run.replies_sent += 1
    else:
        email.status = "awaiting_approval"
        run.drafts_created += 1


def run_mailbox(db: Session, mailbox_id: int, trigger: str = "scheduled") -> RunLog:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise ValueError(f"Mailbox {mailbox_id} not found")

    run = RunLog(mailbox_id=mailbox.id, trigger=trigger, status="running")
    db.add(run)
    db.commit()

    try:
        agent = mailbox.agent
        if agent is None:
            raise RuntimeError("No agent configured for this mailbox")

        fetched = _fetch_into_db(db, mailbox)
        run.emails_fetched = len(fetched)

        client, default_model = llm.get_llm(db)
        model = agent.model or default_model

        # Also picks up leftovers from previous runs that failed mid-way.
        pending = (
            db.query(Email)
            .filter(Email.mailbox_id == mailbox.id, Email.status == "new")
            .order_by(Email.imap_uid)
            .all()
        )
        for email in pending:
            try:
                _process_email(db, mailbox, agent, client, model, email, run)
                email.error = None
            except Exception as exc:  # keep going on per-email failures
                logger.exception("Failed to process email %s", email.id)
                email.status = "error"
                email.error = str(exc)[:2000]
            run.emails_processed += 1
            db.commit()

        agent.last_run_at = _utcnow()
        # Report every mail this run touched — fetched (incl. auto-ignored) and
        # processed (incl. leftovers) — deduped by id, each with its final outcome.
        touched = {e.id: e for e in fetched}
        touched.update({e.id: e for e in pending})
        run.report = _build_report(touched.values())
        # Unread = not yet handled. Mark every message that reached a terminal state
        # this run as read so it is not reprocessed next tick; errors stay unread and
        # get retried. This is what makes the unread flag the source of truth.
        handled_uids = [e.imap_uid for e in touched.values() if e.status not in ("new", "error")]
        _mark_read(mailbox, handled_uids)
        run.status = "success"
    except Exception as exc:
        logger.exception("Run failed for mailbox %s", mailbox_id)
        # A failed flush poisons the session; roll it back before we can record the
        # failure, otherwise the commit below raises PendingRollbackError and the
        # RunLog stays stuck in "running" forever.
        db.rollback()
        run.status = "error"
        run.error = str(exc)[:2000]
    finally:
        run.finished_at = _utcnow()
        db.commit()
    return run


def run_mailbox_standalone(mailbox_id: int, trigger: str) -> None:
    """Entry point for background execution (scheduler / manual trigger)."""
    db = SessionLocal()
    try:
        run_mailbox(db, mailbox_id, trigger)
    finally:
        db.close()


def process_due_mailboxes() -> None:
    """Called by the scheduler tick: run every mailbox whose interval elapsed."""
    db = SessionLocal()
    try:
        agents = (
            db.query(Agent)
            .join(Mailbox)
            .filter(Agent.enabled.is_(True), Mailbox.active.is_(True))
            .all()
        )
        due = []
        now = _utcnow()
        for agent in agents:
            if agent.last_run_at is None:
                due.append(agent.mailbox_id)
            elif agent.last_run_at + timedelta(minutes=agent.interval_minutes) <= now:
                due.append(agent.mailbox_id)
    finally:
        db.close()

    for mailbox_id in due:
        run_mailbox_standalone(mailbox_id, trigger="scheduled")
