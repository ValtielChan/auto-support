from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..models import Email, Reply
from ..schemas import ReplyOut, ReplyUpdate, ReplyWithEmail
from ..services.agent_runner import send_reply
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/replies", tags=["replies"], dependencies=[Depends(get_current_user)]
)


def _get_or_404(db: Session, reply_id: int) -> Reply:
    reply = db.get(Reply, reply_id)
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found")
    return reply


@router.get("", response_model=list[ReplyWithEmail])
def list_replies(
    status: str = "draft", mailbox_id: int | None = None, db: Session = Depends(get_db)
):
    query = db.query(Reply).options(joinedload(Reply.email)).filter(Reply.status == status)
    if mailbox_id is not None:
        query = query.join(Email, Reply.email_id == Email.id).filter(
            Email.mailbox_id == mailbox_id
        )
    return query.order_by(Reply.id.desc()).all()


@router.put("/{reply_id}", response_model=ReplyOut)
def update_reply(reply_id: int, payload: ReplyUpdate, db: Session = Depends(get_db)):
    reply = _get_or_404(db, reply_id)
    if reply.status != "draft":
        raise HTTPException(status_code=400, detail="Only drafts can be edited")
    reply.body = payload.body
    db.commit()
    db.refresh(reply)
    return reply


@router.post("/{reply_id}/approve", response_model=ReplyOut)
def approve_reply(reply_id: int, db: Session = Depends(get_db)):
    reply = _get_or_404(db, reply_id)
    if reply.status != "draft":
        raise HTTPException(status_code=400, detail="Only drafts can be approved")
    try:
        send_reply(db, reply)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SMTP send failed: {exc}")
    return reply


@router.post("/{reply_id}/reject", response_model=ReplyOut)
def reject_reply(reply_id: int, db: Session = Depends(get_db)):
    reply = _get_or_404(db, reply_id)
    if reply.status != "draft":
        raise HTTPException(status_code=400, detail="Only drafts can be rejected")
    reply.status = "rejected"
    reply.email.status = "ignored"
    db.commit()
    db.refresh(reply)
    return reply
