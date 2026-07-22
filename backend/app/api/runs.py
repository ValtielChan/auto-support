from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..models import RunLog
from ..schemas import RunLogOut
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/runs", tags=["runs"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[RunLogOut])
def list_runs(
    db: Session = Depends(get_db),
    mailbox_id: int | None = None,
    limit: int = Query(default=50, le=200),
):
    query = db.query(RunLog)
    if mailbox_id is not None:
        query = query.filter(RunLog.mailbox_id == mailbox_id)
    return query.order_by(RunLog.id.desc()).limit(limit).all()
