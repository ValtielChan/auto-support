"""LLM calls (classification + reply generation) via any OpenAI-compatible API."""

import json
import re

from openai import OpenAI
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Agent, AppSettings, Document, Email
from . import crypto, providers

CATEGORIES = ("support", "partnership", "marketing", "spam", "other")

MAX_BODY_CHARS = 8000
MAX_DOC_CHARS = 6000


class LLMNotConfigured(Exception):
    pass


def get_llm(db: Session) -> tuple[OpenAI, str]:
    """Return a client for the configured provider and the default model name."""
    row = db.query(AppSettings).first()
    provider_id = "openai"
    api_key = ""
    base_url = None
    model = settings.default_model
    if row:
        provider_id = row.provider or "openai"
        if row.openai_api_key_enc:
            api_key = crypto.decrypt(row.openai_api_key_enc)
        base_url = row.openai_base_url or None
        model = row.default_model or model
    api_key = api_key or settings.openai_api_key
    base_url = base_url or settings.openai_base_url or None
    model = model or providers.get_provider(provider_id).default_model
    if not api_key and not base_url:
        raise LLMNotConfigured(
            "No LLM configured: set an API key (and optionally a base URL) in Settings."
        )
    return providers.build_client(provider_id, api_key, base_url), model


def _chat_json(client: OpenAI, model: str, system: str, user: str) -> dict:
    """Call the model expecting a JSON object back, tolerating endpoints that
    do not support response_format."""
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    try:
        resp = client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except Exception:
        resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or ""
    return _parse_json(content)


def _parse_json(content: str) -> dict:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.S)
    if fenced:
        content = fenced.group(1).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        brace = re.search(r"\{.*\}", content, flags=re.S)
        if brace:
            return json.loads(brace.group(0))
        raise


def _knowledge(agent: Agent, kind: str) -> list:
    """Agent playbooks or facts, tolerating agents loaded without the relationship."""
    return [k for k in getattr(agent, "knowledge_items", []) or [] if k.kind == kind]


def _email_as_text(email: Email) -> str:
    body = (email.body_text or "")[:MAX_BODY_CHARS]
    return (
        f"From: {email.from_address}\n"
        f"Subject: {email.subject}\n"
        f"Date: {email.received_at}\n\n"
        f"{body}"
    )


def classify_email(client: OpenAI, model: str, agent: Agent, email: Email) -> dict:
    playbooks = _knowledge(agent, "playbook")
    playbook_block = ""
    if playbooks:
        playbook_block = (
            "The inbox owner describes the kinds of email they receive and how they "
            "think about them — use this to pick the most accurate category:\n"
            + "\n".join(f"- {p.title}: {(p.body or '')[:400]}" for p in playbooks)
            + "\n\n"
        )
    system = (
        "You are an email triage assistant for a support inbox.\n"
        "Context about the product/service this inbox supports:\n"
        f"{(agent.product_context or 'Not provided.')[:MAX_DOC_CHARS]}\n\n"
        f"{playbook_block}"
        "Classify the incoming email into exactly one category:\n"
        "- support: a customer or user asking for help, reporting a problem, or "
        "asking a question about the product\n"
        "- partnership: business development, collaboration or reseller requests\n"
        "- marketing: promotional emails, newsletters, cold outreach, link exchanges\n"
        "- spam: junk, phishing, irrelevant mass mail\n"
        "- other: anything that does not fit the categories above\n\n"
        'Respond with a JSON object: {"category": "<one of the categories>", '
        '"reason": "<one short sentence>"}'
    )
    result = _chat_json(client, model, system, _email_as_text(email))
    category = str(result.get("category", "other")).lower().strip()
    if category not in CATEGORIES:
        category = "other"
    return {"category": category, "reason": str(result.get("reason", ""))}


def _agent_context(agent: Agent, documents: list[Document]) -> list[str]:
    """Shared prompt blocks describing the product, facts, playbooks and style."""
    facts = _knowledge(agent, "fact")
    playbooks = _knowledge(agent, "playbook")
    parts = ["\n## Product / service you support\n" + (agent.product_context or "Not provided.")[:MAX_DOC_CHARS]]
    if facts:
        parts.append("\n## Product facts (authoritative)")
        for f in facts:
            parts.append(f"- {f.title}: {(f.body or '')[:MAX_DOC_CHARS]}")
    if documents:
        parts.append("\n## Reference documents")
        for doc in documents:
            parts.append(f"\n### {doc.title}\n{(doc.content or '')[:MAX_DOC_CHARS]}")
    if playbooks:
        parts.append("\n## Handling playbooks")
        for p in playbooks:
            parts.append(f"- When {p.title}: {(p.body or '')[:MAX_DOC_CHARS]}")
    if agent.guidelines:
        parts.append("\n## Writing style & tone (follow strictly)\n" + agent.guidelines[:MAX_DOC_CHARS])
    return parts


def draft_reply(
    client: OpenAI,
    model: str,
    agent: Agent,
    documents: list[Document],
    email: Email,
    instruction: str = "",
) -> str:
    """On-demand: write a full reply body for a message, following an instruction.

    Used by the Inbox composer's AI assist — returns plain text ready to edit/send.
    """
    parts = [
        "You are a customer support agent drafting an email reply on behalf of a company.",
        *_agent_context(agent, documents),
    ]
    if agent.language:
        parts.append(f"\nWrite in: {agent.language}.")
    else:
        parts.append("\nWrite in the same language as the customer's email.")
    if agent.signature:
        parts.append("\nEnd with this exact signature:\n" + agent.signature)
    parts.append(
        "\nWrite ONLY the reply body as plain text (no subject line, no markdown, no "
        "JSON, no preamble). Do not invent facts, prices or features not in the context."
    )
    system = "\n".join(parts)
    directive = instruction.strip() or "Write the most appropriate reply to this email."
    user = f"Instruction: {directive}\n\nCustomer email:\n\n" + _email_as_text(email)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
    )
    return (resp.choices[0].message.content or "").strip()


def generate_reply(
    client: OpenAI,
    model: str,
    agent: Agent,
    documents: list[Document],
    email: Email,
    category: str,
    allow_escalation: bool,
) -> dict:
    """Return {"action": "reply"|"escalate"|"ignore", "body": str, "reason": str}.

    Every non-spam email is handed here; the agent decides — guided by its
    playbooks & guidelines — whether to reply (e.g. politely decline a marketing
    offer), escalate, or ignore. When action is "escalate", body is the message to
    send to the CUSTOMER. When action is "ignore", body is empty.
    """
    facts = _knowledge(agent, "fact")
    playbooks = _knowledge(agent, "playbook")
    parts = [
        "You are a customer support agent replying by email on behalf of a company.",
        "\n## Product / service you support\n" + (agent.product_context or "Not provided.")[:MAX_DOC_CHARS],
    ]
    if facts:
        parts.append(
            "\n## Product facts (authoritative — you may rely on these to resolve requests)"
        )
        for f in facts:
            parts.append(f"- {f.title}: {(f.body or '')[:MAX_DOC_CHARS]}")
    if documents:
        parts.append("\n## Reference documents")
        for doc in documents:
            parts.append(f"\n### {doc.title}\n{(doc.content or '')[:MAX_DOC_CHARS]}")
    if playbooks:
        parts.append(
            "\n## Handling playbooks (how to deal with specific situations — follow the "
            "one that matches this email)"
        )
        for p in playbooks:
            parts.append(f"- When {p.title}: {(p.body or '')[:MAX_DOC_CHARS]}")
    if agent.guidelines:
        parts.append("\n## Writing style & tone (follow strictly)\n" + agent.guidelines[:MAX_DOC_CHARS])
    if agent.language:
        parts.append(f"\nAlways write the reply in: {agent.language}.")
    else:
        parts.append("\nWrite the reply in the same language as the customer's email.")
    parts.append(
        "\n## Deciding what to do\n"
        f"This email was classified as: {category}. Choose one action:\n"
        '- "reply": write and send a reply. Use this for genuine support requests, '
        "and for any email a handling playbook above tells you to answer (including "
        "replying to politely decline an offer or partnership).\n"
        '- "ignore": do not answer. Use this when a playbook says to ignore this kind '
        "of email, or when it is unsolicited marketing / cold outreach / irrelevant "
        "and no playbook instructs you to reply.\n"
        "Follow the handling playbooks first; when none applies, default to replying "
        "only if a reply is genuinely warranted, otherwise ignore. Never reply to "
        "obvious spam or phishing."
    )
    if allow_escalation:
        parts.append(
            '- "escalate": if you cannot confidently and safely resolve a request '
            "with the information above, escalate to a human instead of guessing."
        )
        if agent.escalation_criteria:
            parts.append("Escalate in particular when:\n" + agent.escalation_criteria[:MAX_DOC_CHARS])
        parts.append(
            'When escalating, write in "body" a short, polite message to the customer '
            "explaining that their request has been forwarded to the relevant team."
        )
    else:
        parts.append('Escalation is disabled: never use "escalate".')
    if agent.signature:
        parts.append("\nEnd every reply with this exact signature:\n" + agent.signature)
    parts.append(
        "\n## Output format\n"
        "Respond with a JSON object:\n"
        '{"action": "reply" | "escalate" | "ignore", '
        '"body": "<the full plain-text email body, or empty string when ignoring>", '
        '"reason": "<one short sentence explaining your decision>"}\n'
        "For reply/escalate the body must be plain text (no markdown, no HTML), ready "
        "to send as-is. Do not invent facts, prices, links or features that are not in "
        "the context. Never mention that you are an AI unless the guidelines ask you to."
    )
    system = "\n".join(parts)
    user = "Decide how to handle this email and, if replying, write the reply:\n\n" + _email_as_text(email)

    result = _chat_json(client, model, system, user)
    action = str(result.get("action", "reply")).lower().strip()
    if action == "escalate" and not allow_escalation:
        action = "reply"
    if action not in ("reply", "escalate", "ignore"):
        action = "reply"
    reason = str(result.get("reason", ""))
    body = str(result.get("body", "")).strip()
    if action == "ignore":
        return {"action": "ignore", "body": "", "reason": reason}
    if not body:
        raise ValueError("LLM returned an empty reply body")
    return {"action": action, "body": body, "reason": reason}
