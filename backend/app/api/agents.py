from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import Agent, Document, KnowledgeItem, Mailbox
from ..schemas import (
    AgentIn,
    AgentOut,
    DocumentIn,
    DocumentOut,
    KnowledgeItemIn,
    KnowledgeItemOut,
    KnowledgeItemUpdate,
)
from .deps import get_current_user, get_db

router = APIRouter(tags=["agents"], dependencies=[Depends(get_current_user)])


def _agent_for_mailbox(db: Session, mailbox_id: int) -> Agent:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if mailbox.agent is None:
        mailbox.agent = Agent(mailbox_id=mailbox.id)
        db.commit()
        db.refresh(mailbox)
    return mailbox.agent


@router.get("/api/mailboxes/{mailbox_id}/agent", response_model=AgentOut)
def get_agent(mailbox_id: int, db: Session = Depends(get_db)):
    return _agent_for_mailbox(db, mailbox_id)


@router.put("/api/mailboxes/{mailbox_id}/agent", response_model=AgentOut)
def update_agent(mailbox_id: int, payload: AgentIn, db: Session = Depends(get_db)):
    agent = _agent_for_mailbox(db, mailbox_id)
    if payload.escalation_enabled and not payload.escalation_email:
        raise HTTPException(
            status_code=422, detail="Escalation requires an escalation email address"
        )
    for key, value in payload.model_dump().items():
        setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/api/mailboxes/{mailbox_id}/agent/documents", response_model=list[DocumentOut])
def list_documents(mailbox_id: int, db: Session = Depends(get_db)):
    agent = _agent_for_mailbox(db, mailbox_id)
    return (
        db.query(Document).filter(Document.agent_id == agent.id).order_by(Document.id).all()
    )


@router.post(
    "/api/mailboxes/{mailbox_id}/agent/documents",
    response_model=DocumentOut,
    status_code=201,
)
def create_document(mailbox_id: int, payload: DocumentIn, db: Session = Depends(get_db)):
    agent = _agent_for_mailbox(db, mailbox_id)
    doc = Document(agent_id=agent.id, title=payload.title, content=payload.content)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()


# ---- knowledge items: playbooks (per-situation rules) + product facts --------

@router.get(
    "/api/mailboxes/{mailbox_id}/agent/knowledge", response_model=list[KnowledgeItemOut]
)
def list_knowledge(
    mailbox_id: int, kind: str | None = None, db: Session = Depends(get_db)
):
    agent = _agent_for_mailbox(db, mailbox_id)
    query = db.query(KnowledgeItem).filter(KnowledgeItem.agent_id == agent.id)
    if kind:
        query = query.filter(KnowledgeItem.kind == kind)
    return query.order_by(KnowledgeItem.id).all()


@router.post(
    "/api/mailboxes/{mailbox_id}/agent/knowledge",
    response_model=KnowledgeItemOut,
    status_code=201,
)
def create_knowledge(
    mailbox_id: int, payload: KnowledgeItemIn, db: Session = Depends(get_db)
):
    agent = _agent_for_mailbox(db, mailbox_id)
    item = KnowledgeItem(
        agent_id=agent.id, kind=payload.kind, title=payload.title, body=payload.body
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/api/knowledge/{item_id}", response_model=KnowledgeItemOut)
def update_knowledge(
    item_id: int, payload: KnowledgeItemUpdate, db: Session = Depends(get_db)
):
    item = db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    item.title = payload.title
    item.body = payload.body
    db.commit()
    db.refresh(item)
    return item


@router.delete("/api/knowledge/{item_id}", status_code=204)
def delete_knowledge(item_id: int, db: Session = Depends(get_db)):
    item = db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    db.delete(item)
    db.commit()
