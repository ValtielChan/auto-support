from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSettings(Base):
    """Singleton row holding platform-wide LLM configuration."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), default="openai")
    openai_api_key_enc: Mapped[str | None] = mapped_column(Text, default=None)
    openai_base_url: Mapped[str | None] = mapped_column(String(500), default=None)
    default_model: Mapped[str] = mapped_column(String(120), default="gpt-5.6-terra")


class Mailbox(Base):
    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email_address: Mapped[str] = mapped_column(String(320))

    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    imap_username: Mapped[str] = mapped_column(String(320))
    imap_password_enc: Mapped[str] = mapped_column(Text)
    imap_folder: Mapped[str] = mapped_column(String(200), default="INBOX")

    smtp_host: Mapped[str] = mapped_column(String(255))
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    smtp_username: Mapped[str] = mapped_column(String(320))
    smtp_password_enc: Mapped[str] = mapped_column(Text)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Highest IMAP UID already fetched; only messages above it are pulled.
    last_seen_uid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped["Agent | None"] = relationship(
        back_populates="mailbox", uselist=False, cascade="all, delete-orphan"
    )
    emails: Mapped[list["Email"]] = relationship(
        back_populates="mailbox", cascade="all, delete-orphan"
    )
    runs: Mapped[list["RunLog"]] = relationship(
        back_populates="mailbox", cascade="all, delete-orphan"
    )


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(
        ForeignKey("mailboxes.id", ondelete="CASCADE"), unique=True
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    # False = replies land in the approval queue; True = sent immediately.
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False)

    model: Mapped[str | None] = mapped_column(String(120), default=None)
    language: Mapped[str | None] = mapped_column(String(80), default=None)

    product_context: Mapped[str] = mapped_column(Text, default="")
    guidelines: Mapped[str] = mapped_column(Text, default="")
    signature: Mapped[str] = mapped_column(Text, default="")

    escalation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_email: Mapped[str | None] = mapped_column(String(320), default=None)
    escalation_criteria: Mapped[str] = mapped_column(Text, default="")
    notify_customer_on_escalation: Mapped[bool] = mapped_column(Boolean, default=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    mailbox: Mapped[Mailbox] = relationship(back_populates="agent")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class Document(Base):
    """A piece of reference material given to the agent as context."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="documents")


KNOWLEDGE_KINDS = ("playbook", "fact")


class KnowledgeItem(Base):
    """Structured guidance for the agent, split by kind.

    - ``playbook``: title = a situation (e.g. "SEO cold outreach"), body = what to
      do about it. Injected into classification + reply generation.
    - ``fact``: title = a topic (e.g. "Free plan limits"), body = the detail. Given
      to the reply step as authoritative product knowledge the agent may rely on.
    """

    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="knowledge_items")


EMAIL_STATUSES = ("new", "awaiting_approval", "replied", "escalated", "ignored", "error")
EMAIL_CATEGORIES = ("support", "partnership", "marketing", "spam", "other")


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("mailbox_id", "message_id", name="uq_mailbox_message"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"))

    imap_uid: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[str] = mapped_column(String(500))
    from_address: Mapped[str] = mapped_column(String(500))
    to_address: Mapped[str] = mapped_column(String(500), default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[str | None] = mapped_column(String(50), default=None)
    category_reason: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(50), default="new")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # When the agent last processed this email, and why it did what it did
    # (the reply/escalate/ignore decision — distinct from category_reason above).
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    action_reason: Mapped[str | None] = mapped_column(Text, default=None)

    mailbox: Mapped[Mailbox] = relationship(back_populates="emails")
    replies: Mapped[list["Reply"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )


REPLY_STATUSES = ("draft", "sent", "rejected")


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    model_used: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    email: Mapped[Email] = relationship(back_populates="replies")


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"))
    trigger: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled | manual
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | success | error
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    emails_fetched: Mapped[int] = mapped_column(Integer, default=0)
    emails_processed: Mapped[int] = mapped_column(Integer, default=0)
    replies_sent: Mapped[int] = mapped_column(Integer, default=0)
    drafts_created: Mapped[int] = mapped_column(Integer, default=0)
    escalated: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # JSON array: one entry per email this run fetched or processed, with its
    # final outcome (status) and the reason (classification reason or error).
    report: Mapped[str | None] = mapped_column(Text, default=None)

    mailbox: Mapped[Mailbox] = relationship(back_populates="runs")
