from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models import Agent, Email, Mailbox, Reply, RunLog
from ..schemas import DashboardStats
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)]
)


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db)):
    return DashboardStats(
        mailboxes=db.query(Mailbox).count(),
        agents_enabled=db.query(Agent).filter(Agent.enabled.is_(True)).count(),
        emails_total=db.query(Email).count(),
        pending_drafts=db.query(Reply).filter(Reply.status == "draft").count(),
        replied=db.query(Email).filter(Email.status == "replied").count(),
        escalated=db.query(Email).filter(Email.status == "escalated").count(),
        last_runs=db.query(RunLog).order_by(RunLog.id.desc()).limit(10).all(),
    )
