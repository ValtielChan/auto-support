import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------- auth

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


# ---------------------------------------------------------------- mailboxes

class MailboxBase(BaseModel):
    name: str
    email_address: str
    imap_host: str
    imap_port: int = 993
    imap_ssl: bool = True
    imap_username: str
    imap_folder: str = "INBOX"
    smtp_host: str
    smtp_port: int = 587
    smtp_tls: bool = True
    smtp_username: str
    active: bool = True


class MailboxCreate(MailboxBase):
    imap_password: str
    smtp_password: str


class MailboxUpdate(MailboxBase):
    # Empty password fields mean "keep the stored one".
    imap_password: str = ""
    smtp_password: str = ""


class MailboxOut(MailboxBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_seen_uid: int
    created_at: datetime


class ConnectionTestResult(BaseModel):
    imap_ok: bool
    imap_detail: str
    smtp_ok: bool
    smtp_detail: str


# ---------------------------------------------------------------- agent

class AgentIn(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(default=60, ge=1)
    auto_send: bool = False
    model: str | None = None
    language: str | None = None
    product_context: str = ""
    guidelines: str = ""
    signature: str = ""
    escalation_enabled: bool = False
    escalation_email: str | None = None
    escalation_criteria: str = ""
    notify_customer_on_escalation: bool = True


class AgentOut(AgentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mailbox_id: int
    last_run_at: datetime | None


# ---------------------------------------------------------------- documents

class DocumentIn(BaseModel):
    title: str
    content: str


class DocumentOut(DocumentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    agent_id: int
    created_at: datetime


# ---------------------------------------------------------------- knowledge (playbooks / facts)

class KnowledgeItemIn(BaseModel):
    kind: str
    title: str
    body: str = ""

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v):
        if v not in ("playbook", "fact"):
            raise ValueError("kind must be 'playbook' or 'fact'")
        return v


class KnowledgeItemUpdate(BaseModel):
    title: str
    body: str = ""


class KnowledgeItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    agent_id: int
    kind: str
    title: str
    body: str
    created_at: datetime


# ---------------------------------------------------------------- emails / replies

class ReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email_id: int
    body: str
    status: str
    model_used: str | None
    created_at: datetime
    sent_at: datetime | None


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mailbox_id: int
    imap_uid: int
    message_id: str
    from_address: str
    to_address: str
    subject: str
    received_at: datetime | None
    fetched_at: datetime
    category: str | None
    category_reason: str | None
    status: str
    error: str | None


class EmailDetail(EmailOut):
    body_text: str
    replies: list[ReplyOut] = []


class EmailList(BaseModel):
    items: list[EmailOut]
    total: int


class ReplyWithEmail(ReplyOut):
    email: EmailDetail


class ReplyUpdate(BaseModel):
    body: str


# ---------------------------------------------------------------- runs

class RunEmailReport(BaseModel):
    email_id: int
    from_address: str
    subject: str
    category: str | None = None
    status: str
    reason: str | None = None


class RunLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mailbox_id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    emails_fetched: int
    emails_processed: int
    replies_sent: int
    drafts_created: int
    escalated: int
    error: str | None
    report: list[RunEmailReport] = []

    @field_validator("report", mode="before")
    @classmethod
    def _parse_report(cls, v):
        # Stored as a JSON string in the DB; expose it as a parsed list.
        if isinstance(v, str):
            return json.loads(v) if v else []
        return v or []


# ---------------------------------------------------------------- inbox (live mailbox)

class InboxItem(BaseModel):
    uid: int
    message_id: str
    from_address: str
    subject: str
    received_at: datetime | None
    seen: bool
    # The agent's take on this message, when it has ingested it (matched by message_id).
    agent_email_id: int | None = None
    agent_status: str | None = None
    agent_category: str | None = None
    agent_reason: str | None = None


class InboxReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    body: str
    status: str
    model_used: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class InboxAgentDetail(BaseModel):
    """Everything the agent recorded about a message: when, what, why."""
    email_id: int
    status: str
    category: str | None = None
    category_reason: str | None = None
    action_reason: str | None = None
    processed_at: datetime | None = None
    fetched_at: datetime | None = None
    error: str | None = None
    replies: list[InboxReplyOut] = []


class InboxMessage(InboxItem):
    to_address: str = ""
    body_text: str = ""
    body_html: str = ""
    agent: InboxAgentDetail | None = None


class InboxList(BaseModel):
    items: list[InboxItem]


class InboxFlagIn(BaseModel):
    uids: list[int]
    seen: bool


class InboxDeleteIn(BaseModel):
    uids: list[int]


class InboxReplyIn(BaseModel):
    body: str


class InboxSuggestIn(BaseModel):
    instruction: str = ""


class InboxSuggestOut(BaseModel):
    body: str


# ---------------------------------------------------------------- settings

class SettingsOut(BaseModel):
    provider: str
    has_api_key: bool
    api_key_hint: str
    openai_base_url: str
    default_model: str


class SettingsIn(BaseModel):
    provider: str = "openai"
    # Empty api_key means "keep the stored one"; "-" means "clear it".
    openai_api_key: str = ""
    openai_base_url: str = ""
    default_model: str = ""


class ProviderOut(BaseModel):
    id: str
    label: str
    needs_base_url: bool
    default_model: str


class ModelsOut(BaseModel):
    provider: str
    source: str  # curated | live | none
    models: list[str]


# ---------------------------------------------------------------- assistant

class AssistantMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AssistantChatIn(BaseModel):
    messages: list[AssistantMessage]


class AssistantChatOut(BaseModel):
    reply: str
    actions: list[str]
    changed: bool


# ---------------------------------------------------------------- dashboard

class DashboardStats(BaseModel):
    mailboxes: int
    agents_enabled: int
    emails_total: int
    pending_drafts: int
    replied: int
    escalated: int
    last_runs: list[RunLogOut]
