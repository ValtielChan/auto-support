from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import Agent, Mailbox, User
from ..schemas import ConnectionTestResult, MailboxCreate, MailboxOut, MailboxUpdate
from ..services import crypto, imap_client, smtp_client
from ..services.agent_runner import run_mailbox_standalone
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/mailboxes", tags=["mailboxes"], dependencies=[Depends(get_current_user)]
)


def _get_or_404(db: Session, mailbox_id: int) -> Mailbox:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mailbox


def _test(imap_kwargs: dict, smtp_kwargs: dict) -> ConnectionTestResult:
    imap_ok, smtp_ok = True, True
    try:
        imap_detail = imap_client.test_connection(**imap_kwargs)
    except Exception as exc:
        imap_ok, imap_detail = False, f"{type(exc).__name__}: {exc}"
    try:
        smtp_detail = smtp_client.test_connection(**smtp_kwargs)
    except Exception as exc:
        smtp_ok, smtp_detail = False, f"{type(exc).__name__}: {exc}"
    return ConnectionTestResult(
        imap_ok=imap_ok, imap_detail=imap_detail, smtp_ok=smtp_ok, smtp_detail=smtp_detail
    )


@router.get("", response_model=list[MailboxOut])
def list_mailboxes(db: Session = Depends(get_db)):
    return db.query(Mailbox).order_by(Mailbox.id).all()


@router.post("", response_model=MailboxOut, status_code=201)
def create_mailbox(payload: MailboxCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    imap_password = data.pop("imap_password")
    smtp_password = data.pop("smtp_password")
    mailbox = Mailbox(
        **data,
        imap_password_enc=crypto.encrypt(imap_password),
        smtp_password_enc=crypto.encrypt(smtp_password),
    )
    # Every mailbox gets an agent row immediately (disabled by default).
    mailbox.agent = Agent()
    db.add(mailbox)
    db.commit()
    db.refresh(mailbox)
    return mailbox


@router.get("/{mailbox_id}", response_model=MailboxOut)
def get_mailbox(mailbox_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, mailbox_id)


@router.put("/{mailbox_id}", response_model=MailboxOut)
def update_mailbox(mailbox_id: int, payload: MailboxUpdate, db: Session = Depends(get_db)):
    mailbox = _get_or_404(db, mailbox_id)
    data = payload.model_dump()
    imap_password = data.pop("imap_password")
    smtp_password = data.pop("smtp_password")
    for key, value in data.items():
        setattr(mailbox, key, value)
    if imap_password:
        mailbox.imap_password_enc = crypto.encrypt(imap_password)
    if smtp_password:
        mailbox.smtp_password_enc = crypto.encrypt(smtp_password)
    db.commit()
    db.refresh(mailbox)
    return mailbox


@router.delete("/{mailbox_id}", status_code=204)
def delete_mailbox(mailbox_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, mailbox_id))
    db.commit()


@router.post("/test", response_model=ConnectionTestResult)
def test_new_mailbox(payload: MailboxCreate):
    """Test credentials before saving anything."""
    return _test(
        imap_kwargs=dict(
            host=payload.imap_host,
            port=payload.imap_port,
            use_ssl=payload.imap_ssl,
            username=payload.imap_username,
            password=payload.imap_password,
            folder=payload.imap_folder,
        ),
        smtp_kwargs=dict(
            host=payload.smtp_host,
            port=payload.smtp_port,
            use_tls=payload.smtp_tls,
            username=payload.smtp_username,
            password=payload.smtp_password,
        ),
    )


@router.post("/{mailbox_id}/test", response_model=ConnectionTestResult)
def test_saved_mailbox(mailbox_id: int, db: Session = Depends(get_db)):
    mailbox = _get_or_404(db, mailbox_id)
    return _test(
        imap_kwargs=dict(
            host=mailbox.imap_host,
            port=mailbox.imap_port,
            use_ssl=mailbox.imap_ssl,
            username=mailbox.imap_username,
            password=crypto.decrypt(mailbox.imap_password_enc),
            folder=mailbox.imap_folder,
        ),
        smtp_kwargs=dict(
            host=mailbox.smtp_host,
            port=mailbox.smtp_port,
            use_tls=mailbox.smtp_tls,
            username=mailbox.smtp_username,
            password=crypto.decrypt(mailbox.smtp_password_enc),
        ),
    )


@router.post("/{mailbox_id}/run", status_code=202)
def run_now(mailbox_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    mailbox = _get_or_404(db, mailbox_id)
    if mailbox.agent is None:
        raise HTTPException(status_code=400, detail="No agent configured for this mailbox")
    background.add_task(run_mailbox_standalone, mailbox.id, "manual")
    return {"status": "started"}
