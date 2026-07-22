from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models import Email
from ..schemas import EmailDetail, EmailList
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/emails", tags=["emails"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=EmailList)
def list_emails(
    db: Session = Depends(get_db),
    mailbox_id: int | None = None,
    status: str | None = None,
    category: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    query = db.query(Email)
    if mailbox_id is not None:
        query = query.filter(Email.mailbox_id == mailbox_id)
    if status:
        query = query.filter(Email.status == status)
    if category:
        query = query.filter(Email.category == category)
    total = query.count()
    items = query.order_by(Email.id.desc()).offset(offset).limit(limit).all()
    return EmailList(items=items, total=total)


@router.get("/{email_id}", response_model=EmailDetail)
def get_email(email_id: int, db: Session = Depends(get_db)):
    email = db.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return email
