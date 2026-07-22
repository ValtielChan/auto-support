"""Live mailbox ('augmented inbox'): browse the real IMAP folder, toggle read/
unread, reply and delete - merged with the agent's verdict on each message."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models import Email, Mailbox
from ..schemas import (
    InboxAgentDetail,
    InboxDeleteIn,
    InboxFlagIn,
    InboxList,
    InboxMessage,
    InboxReplyIn,
    InboxReplyOut,
    InboxSuggestIn,
    InboxSuggestOut,
)
from ..services import bbcode, crypto, imap_client, llm, smtp_client
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/mailboxes", tags=["inbox"], dependencies=[Depends(get_current_user)]
)


def _mailbox(db: Session, mailbox_id: int) -> Mailbox:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mailbox


def _imap_args(mailbox: Mailbox) -> dict:
    return dict(
        host=mailbox.imap_host,
        port=mailbox.imap_port,
        use_ssl=mailbox.imap_ssl,
        username=mailbox.imap_username,
        password=crypto.decrypt(mailbox.imap_password_enc),
        folder=mailbox.imap_folder,
    )


def _verdicts(db: Session, mailbox_id: int, message_ids: list[str]) -> dict:
    """Map message_id -> the agent's ingested Email row, for the given messages."""
    if not message_ids:
        return {}
    rows = (
        db.query(Email)
        .filter(Email.mailbox_id == mailbox_id, Email.message_id.in_(message_ids))
        .all()
    )
    return {e.message_id: e for e in rows}


@router.get("/{mailbox_id}/inbox", response_model=InboxList)
def list_inbox(
    mailbox_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    mailbox = _mailbox(db, mailbox_id)
    try:
        messages = imap_client.list_mailbox(**_imap_args(mailbox), limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}")
    verdicts = _verdicts(db, mailbox_id, [m["message_id"] for m in messages if m["message_id"]])
    items = []
    for m in messages:
        e = verdicts.get(m["message_id"])
        items.append(
            {
                **m,
                "agent_email_id": e.id if e else None,
                "agent_status": e.status if e else None,
                "agent_category": e.category if e else None,
                "agent_reason": (e.error if e and e.status == "error" else (e.action_reason or e.category_reason) if e else None),
            }
        )
    return InboxList(items=items)


@router.get("/{mailbox_id}/inbox/{uid}", response_model=InboxMessage)
def get_inbox_message(mailbox_id: int, uid: int, db: Session = Depends(get_db)):
    mailbox = _mailbox(db, mailbox_id)
    try:
        m = imap_client.fetch_message(**_imap_args(mailbox), uid=uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}")
    e = _verdicts(db, mailbox_id, [m["message_id"]]).get(m["message_id"])
    agent_detail = None
    if e:
        agent_detail = InboxAgentDetail(
            email_id=e.id,
            status=e.status,
            category=e.category,
            category_reason=e.category_reason,
            action_reason=e.action_reason,
            processed_at=e.processed_at,
            fetched_at=e.fetched_at,
            error=e.error,
            replies=[
                InboxReplyOut.model_validate(r)
                for r in sorted(e.replies, key=lambda r: r.id)
            ],
        )
    return InboxMessage(
        uid=m["imap_uid"],
        message_id=m["message_id"],
        from_address=m["from_address"],
        to_address=m.get("to_address", ""),
        subject=m["subject"],
        received_at=m.get("received_at"),
        seen=m.get("seen", False),
        body_text=m.get("body_text", ""),
        body_html=m.get("body_html", ""),
        agent_email_id=e.id if e else None,
        agent_status=e.status if e else None,
        agent_category=e.category if e else None,
        agent_reason=(e.error if e and e.status == "error" else (e.action_reason or e.category_reason) if e else None),
        agent=agent_detail,
    )


@router.post("/{mailbox_id}/inbox/flags", status_code=204)
def set_inbox_flags(mailbox_id: int, payload: InboxFlagIn, db: Session = Depends(get_db)):
    mailbox = _mailbox(db, mailbox_id)
    try:
        imap_client.set_seen(**_imap_args(mailbox), uids=payload.uids, seen=payload.seen)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}")


@router.post("/{mailbox_id}/inbox/delete", status_code=204)
def delete_inbox_messages(mailbox_id: int, payload: InboxDeleteIn, db: Session = Depends(get_db)):
    mailbox = _mailbox(db, mailbox_id)
    try:
        imap_client.delete_messages(**_imap_args(mailbox), uids=payload.uids)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}")


@router.post("/{mailbox_id}/inbox/{uid}/reply", status_code=204)
def reply_inbox_message(
    mailbox_id: int, uid: int, payload: InboxReplyIn, db: Session = Depends(get_db)
):
    mailbox = _mailbox(db, mailbox_id)
    if not payload.body.strip():
        raise HTTPException(status_code=422, detail="Reply body is empty")
    try:
        original = imap_client.fetch_message(**_imap_args(mailbox), uid=uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}")
    subject = original["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    # The composer speaks BBCode; send a plain-text body plus an HTML alternative.
    try:
        smtp_client.send_email(
            host=mailbox.smtp_host,
            port=mailbox.smtp_port,
            use_tls=mailbox.smtp_tls,
            username=mailbox.smtp_username,
            password=crypto.decrypt(mailbox.smtp_password_enc),
            from_name=mailbox.name,
            from_addr=mailbox.email_address,
            to_addr=original["from_address"],
            subject=subject,
            body=bbcode.to_plain(payload.body),
            html=bbcode.to_html(payload.body),
            in_reply_to=original["message_id"] or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SMTP error: {exc}")


@router.post("/{mailbox_id}/inbox/{uid}/suggest", response_model=InboxSuggestOut)
def suggest_reply(
    mailbox_id: int, uid: int, payload: InboxSuggestIn, db: Session = Depends(get_db)
):
    mailbox = _mailbox(db, mailbox_id)
    agent = mailbox.agent
    if agent is None:
        raise HTTPException(status_code=422, detail="No agent configured for this mailbox")
    try:
        m = imap_client.fetch_message(**_imap_args(mailbox), uid=uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP error: {exc}")
    # Transient (not persisted) Email just to carry context into the drafting prompt.
    transient = Email(
        from_address=m["from_address"],
        subject=m["subject"],
        received_at=m.get("received_at"),
        body_text=m.get("body_text", ""),
    )
    try:
        client, default_model = llm.get_llm(db)
    except llm.LLMNotConfigured as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    model = agent.model or default_model
    try:
        body = llm.draft_reply(client, model, agent, agent.documents, transient, payload.instruction)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}")
    return InboxSuggestOut(body=body)
