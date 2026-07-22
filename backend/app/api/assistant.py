from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import Mailbox
from ..schemas import AssistantChatIn, AssistantChatOut
from ..services import assistant
from ..services.llm import LLMNotConfigured
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api/mailboxes", tags=["assistant"], dependencies=[Depends(get_current_user)]
)


@router.post("/{mailbox_id}/assistant", response_model=AssistantChatOut)
def assistant_chat(mailbox_id: int, payload: AssistantChatIn, db: Session = Depends(get_db)):
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if mailbox.agent is None:
        raise HTTPException(status_code=400, detail="No agent configured for this mailbox")
    if not payload.messages or payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="Last message must be from the user")
    try:
        result = assistant.chat(db, mailbox, [m.model_dump() for m in payload.messages])
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}")
    return AssistantChatOut(**result)
