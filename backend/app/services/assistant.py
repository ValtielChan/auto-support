"""In-app configuration copilot.

A tool-calling LLM agent embedded in the UI: the user talks to it in natural
language and it can read and modify everything configurable on a mailbox —
agent settings, product context, guidelines, documents… The same fields the
user can edit by hand, nothing more (credentials are out of reach).
"""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Agent, Document, Email, KnowledgeItem, Mailbox
from . import crypto, imap_client, llm, smtp_client
from .providers import get_provider, list_models

MAX_ROUNDS = 8

# Agent fields the copilot may update, mirroring the manual form.
AGENT_FIELDS = (
    "enabled",
    "interval_minutes",
    "auto_send",
    "model",
    "language",
    "product_context",
    "guidelines",
    "signature",
    "escalation_enabled",
    "escalation_email",
    "escalation_criteria",
    "notify_customer_on_escalation",
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_agent_config",
            "description": "Read the current support-agent configuration for this mailbox.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_agent_config",
            "description": (
                "Update one or more fields of the support-agent configuration. "
                "Only pass the fields you want to change; the others are kept."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "Run automatically on schedule"},
                    "interval_minutes": {"type": "integer", "minimum": 1},
                    "auto_send": {
                        "type": "boolean",
                        "description": "true = send replies immediately, false = human approval queue",
                    },
                    "model": {"type": "string", "description": "LLM model id, empty string = platform default"},
                    "language": {"type": "string", "description": "Forced reply language, empty = customer's language"},
                    "product_context": {"type": "string", "description": "General product/service overview"},
                    "guidelines": {"type": "string", "description": "Writing style and tone ONLY (not per-situation rules — use playbooks for those)"},
                    "signature": {"type": "string"},
                    "escalation_enabled": {"type": "boolean"},
                    "escalation_email": {"type": "string"},
                    "escalation_criteria": {"type": "string"},
                    "notify_customer_on_escalation": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List the agent's reference documents (id, title, size).",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_content": {"type": "boolean", "description": "Also return full contents"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document",
            "description": "Read one reference document in full.",
            "parameters": {
                "type": "object",
                "properties": {"document_id": {"type": "integer"}},
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_document",
            "description": "Add a reference document (FAQ, product docs, troubleshooting guide…).",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_document",
            "description": "Rewrite a reference document's title and/or content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_document",
            "description": "Delete a reference document.",
            "parameters": {
                "type": "object",
                "properties": {"document_id": {"type": "integer"}},
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_knowledge",
            "description": (
                "List the agent's structured knowledge: playbooks (per-situation "
                "handling rules) and/or facts (product specifics). "
                "kind is 'playbook', 'fact', or omitted for both."
            ),
            "parameters": {
                "type": "object",
                "properties": {"kind": {"type": "string", "enum": ["playbook", "fact"]}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_knowledge",
            "description": (
                "Add a knowledge item. kind='playbook': title = the situation/email "
                "type (e.g. 'SEO cold outreach'), body = what the agent should do. "
                "kind='fact': title = a product topic (e.g. 'Free plan limits'), body "
                "= the authoritative detail the agent may use to resolve requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["playbook", "fact"]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["kind", "title", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_knowledge",
            "description": "Rewrite a knowledge item's title and/or body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_knowledge",
            "description": "Delete a knowledge item (playbook or fact).",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_mailbox",
            "description": "Update basic mailbox settings (not the IMAP/SMTP credentials).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Display name"},
                    "active": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_emails",
            "description": "List the most recent ingested emails (subject, sender, category, status).",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_inbox",
            "description": (
                "Browse the LIVE mailbox over IMAP: recent messages with their "
                "read/unread flag and the agent's verdict. Use this to see the real "
                "inbox, not just what the agent ingested."
            ),
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_inbox_message",
            "description": "Read one live message in full by its IMAP uid (does not mark it read).",
            "parameters": {
                "type": "object",
                "properties": {"uid": {"type": "integer"}},
                "required": ["uid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_inbox_read",
            "description": "Mark one or more live messages read (seen=true) or unread (seen=false).",
            "parameters": {
                "type": "object",
                "properties": {
                    "uids": {"type": "array", "items": {"type": "integer"}},
                    "seen": {"type": "boolean"},
                },
                "required": ["uids", "seen"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_inbox_message",
            "description": "Send a reply to a live message by uid (SMTP, threaded). Only do this when the user asks.",
            "parameters": {
                "type": "object",
                "properties": {"uid": {"type": "integer"}, "body": {"type": "string"}},
                "required": ["uid", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_inbox_messages",
            "description": "Permanently delete one or more live messages by uid. Destructive — confirm with the user first.",
            "parameters": {
                "type": "object",
                "properties": {"uids": {"type": "array", "items": {"type": "integer"}}},
                "required": ["uids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_models",
            "description": "List the LLM models available with the platform's configured provider.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

ACTION_LABELS = {
    "update_agent_config": "Agent configuration updated",
    "add_document": "Document added",
    "update_document": "Document updated",
    "delete_document": "Document deleted",
    "add_knowledge": "Knowledge item added",
    "update_knowledge": "Knowledge item updated",
    "delete_knowledge": "Knowledge item deleted",
    "set_inbox_read": "Mailbox flags updated",
    "reply_inbox_message": "Reply sent",
    "delete_inbox_messages": "Messages deleted",
    "update_mailbox": "Mailbox updated",
}

WRITE_TOOLS = set(ACTION_LABELS)


def _agent_snapshot(agent: Agent) -> dict:
    snap = {f: getattr(agent, f) for f in AGENT_FIELDS}
    snap["last_run_at"] = agent.last_run_at.isoformat() if agent.last_run_at else None
    return snap


def _system_prompt(db: Session, mailbox: Mailbox) -> str:
    agent = mailbox.agent
    docs = [
        {"id": d.id, "title": d.title, "chars": len(d.content)}
        for d in (agent.documents if agent else [])
    ]
    knowledge = [
        {"id": k.id, "kind": k.kind, "title": k.title}
        for k in (agent.knowledge_items if agent else [])
    ]
    return (
        "You are the configuration copilot of Auto Support, a platform where each "
        "mailbox has an AI support agent that reads incoming email on a schedule, "
        "classifies it, and replies to support requests (directly or via a human "
        "approval queue), with optional escalation to a human team.\n\n"
        "You help the user configure the agent of the CURRENT mailbox through "
        "conversation, using your tools. You can do everything the user could do "
        "by hand in the form. The agent's guidance is organized as:\n"
        "- product_context: a general overview of the product/service.\n"
        "- guidelines: writing STYLE & TONE only.\n"
        "- signature: appended to every reply.\n"
        "- playbooks (knowledge, kind='playbook'): per-situation rules — for each "
        "type of email (support request, SEO outreach, marketplace partner…), what "
        "the agent should do. This is where per-case behavior lives, NOT guidelines.\n"
        "- facts (knowledge, kind='fact'): discrete authoritative product specifics "
        "(limits, pricing, how a feature works) the agent can use to resolve requests.\n"
        "- documents: long-form reference material (FAQ, guides).\n\n"
        "You can also browse and act on the LIVE mailbox over IMAP (list_inbox, "
        "read_inbox_message), and — only when the user explicitly asks — mark "
        "messages read/unread, send replies, or delete messages. Always confirm "
        "before deleting.\n\n"
        "Guidance:\n"
        "- When the user roughly describes their product, write a COMPLETE, "
        "well-structured product context — expand and structure rather than copying "
        "their words verbatim. Put per-situation handling into playbooks and concrete "
        "product specifics into facts, rather than dumping everything into guidelines. "
        "Ask a short clarifying question only when something essential is missing.\n"
        "- Apply changes with tools, then confirm briefly what you changed. "
        "Don't paste entire rewritten texts back into the chat; summarize.\n"
        "- Warn the user before enabling auto_send (replies leave without review).\n"
        "- Answer in the user's language.\n\n"
        f"Current date: {datetime.now(timezone.utc).date().isoformat()}\n"
        f"Mailbox: {json.dumps({'id': mailbox.id, 'name': mailbox.name, 'email': mailbox.email_address, 'active': mailbox.active})}\n"
        f"Agent config: {json.dumps(_agent_snapshot(agent), default=str) if agent else 'none'}\n"
        f"Documents: {json.dumps(docs)}\n"
        f"Knowledge (playbooks & facts): {json.dumps(knowledge)}"
    )


def _execute(db: Session, mailbox: Mailbox, name: str, args: dict):
    agent = mailbox.agent
    if name == "get_agent_config":
        return _agent_snapshot(agent)

    if name == "update_agent_config":
        unknown = [k for k in args if k not in AGENT_FIELDS]
        if unknown:
            return {"error": f"Unknown fields: {unknown}"}
        merged = {**_agent_snapshot(agent), **args}
        if merged["escalation_enabled"] and not merged["escalation_email"]:
            return {"error": "escalation_enabled requires escalation_email to be set"}
        if "interval_minutes" in args and args["interval_minutes"] < 1:
            return {"error": "interval_minutes must be >= 1"}
        for key, value in args.items():
            setattr(agent, key, value if value != "" or key in ("product_context", "guidelines", "signature", "escalation_criteria") else None)
        db.commit()
        return {"ok": True, "config": _agent_snapshot(agent)}

    if name == "list_documents":
        docs = db.query(Document).filter(Document.agent_id == agent.id).order_by(Document.id).all()
        include = bool(args.get("include_content"))
        return [
            {"id": d.id, "title": d.title, "chars": len(d.content), **({"content": d.content} if include else {})}
            for d in docs
        ]

    if name in ("get_document", "update_document", "delete_document"):
        doc = db.get(Document, int(args["document_id"]))
        if doc is None or doc.agent_id != agent.id:
            return {"error": "Document not found on this mailbox"}
        if name == "get_document":
            return {"id": doc.id, "title": doc.title, "content": doc.content}
        if name == "update_document":
            if args.get("title"):
                doc.title = args["title"]
            if args.get("content") is not None and "content" in args:
                doc.content = args["content"]
            db.commit()
            return {"ok": True, "id": doc.id, "title": doc.title, "chars": len(doc.content)}
        db.delete(doc)
        db.commit()
        return {"ok": True}

    if name == "add_document":
        doc = Document(agent_id=agent.id, title=args["title"], content=args["content"])
        db.add(doc)
        db.commit()
        return {"ok": True, "id": doc.id}

    if name == "list_knowledge":
        query = db.query(KnowledgeItem).filter(KnowledgeItem.agent_id == agent.id)
        if args.get("kind"):
            query = query.filter(KnowledgeItem.kind == args["kind"])
        return [
            {"id": k.id, "kind": k.kind, "title": k.title, "body": k.body}
            for k in query.order_by(KnowledgeItem.id).all()
        ]

    if name == "add_knowledge":
        if args.get("kind") not in ("playbook", "fact"):
            return {"error": "kind must be 'playbook' or 'fact'"}
        item = KnowledgeItem(
            agent_id=agent.id,
            kind=args["kind"],
            title=args.get("title", ""),
            body=args.get("body", ""),
        )
        db.add(item)
        db.commit()
        return {"ok": True, "id": item.id, "kind": item.kind}

    if name in ("update_knowledge", "delete_knowledge"):
        item = db.get(KnowledgeItem, int(args["item_id"]))
        if item is None or item.agent_id != agent.id:
            return {"error": "Knowledge item not found on this mailbox"}
        if name == "delete_knowledge":
            db.delete(item)
            db.commit()
            return {"ok": True}
        if args.get("title"):
            item.title = args["title"]
        if "body" in args and args["body"] is not None:
            item.body = args["body"]
        db.commit()
        return {"ok": True, "id": item.id, "title": item.title}

    if name == "update_mailbox":
        if "name" in args and args["name"]:
            mailbox.name = args["name"]
        if "active" in args:
            mailbox.active = bool(args["active"])
        db.commit()
        return {"ok": True, "name": mailbox.name, "active": mailbox.active}

    if name == "get_recent_emails":
        limit = min(int(args.get("limit", 10)), 50)
        emails = (
            db.query(Email)
            .filter(Email.mailbox_id == mailbox.id)
            .order_by(Email.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "from": e.from_address,
                "subject": e.subject,
                "category": e.category,
                "status": e.status,
                "received_at": e.received_at.isoformat() if e.received_at else None,
            }
            for e in emails
        ]

    if name in (
        "list_inbox",
        "read_inbox_message",
        "set_inbox_read",
        "reply_inbox_message",
        "delete_inbox_messages",
    ):
        imap_args = dict(
            host=mailbox.imap_host,
            port=mailbox.imap_port,
            use_ssl=mailbox.imap_ssl,
            username=mailbox.imap_username,
            password=crypto.decrypt(mailbox.imap_password_enc),
            folder=mailbox.imap_folder,
        )
        if name == "list_inbox":
            msgs = imap_client.list_mailbox(**imap_args, limit=min(int(args.get("limit", 30)), 100))
            verdicts = {
                e.message_id: e
                for e in db.query(Email).filter(
                    Email.mailbox_id == mailbox.id,
                    Email.message_id.in_([m["message_id"] for m in msgs if m["message_id"]]),
                )
            }
            return [
                {
                    "uid": m["uid"],
                    "from": m["from_address"],
                    "subject": m["subject"],
                    "seen": m["seen"],
                    "agent_status": (verdicts.get(m["message_id"]).status if verdicts.get(m["message_id"]) else None),
                    "agent_category": (verdicts.get(m["message_id"]).category if verdicts.get(m["message_id"]) else None),
                }
                for m in msgs
            ]
        if name == "read_inbox_message":
            m = imap_client.fetch_message(**imap_args, uid=int(args["uid"]))
            return {
                "uid": m["imap_uid"],
                "from": m["from_address"],
                "subject": m["subject"],
                "seen": m.get("seen"),
                "body": (m.get("body_text") or "")[:6000],
            }
        if name == "set_inbox_read":
            imap_client.set_seen(**imap_args, uids=args["uids"], seen=bool(args["seen"]))
            return {"ok": True, "uids": args["uids"], "seen": bool(args["seen"])}
        if name == "delete_inbox_messages":
            imap_client.delete_messages(**imap_args, uids=args["uids"])
            return {"ok": True, "deleted": args["uids"]}
        # reply_inbox_message
        original = imap_client.fetch_message(**imap_args, uid=int(args["uid"]))
        subject = original["subject"]
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        smtp_client.send_email(
            host=mailbox.smtp_host,
            port=mailbox.smtp_port,
            use_tls=mailbox.smtp_tls,
            username=mailbox.smtp_username,
            password=crypto.decrypt(mailbox.smtp_password_enc),
            from_name=mailbox.name,
            from_addr=mailbox.email_address,
            to_addr=original["from_address"],
            subject=subject,
            body=args["body"],
            in_reply_to=original["message_id"] or None,
        )
        return {"ok": True, "to": original["from_address"]}

    if name == "get_available_models":
        from ..config import settings as env_settings
        from ..models import AppSettings

        # NB: do NOT re-import crypto here — it's imported at module level. A local
        # `from . import crypto` would make `crypto` function-local everywhere in
        # _execute, breaking the inbox tools above (UnboundLocalError).
        row = db.query(AppSettings).first()
        provider_id = (row.provider if row else None) or "openai"
        api_key = crypto.decrypt(row.openai_api_key_enc) if row and row.openai_api_key_enc else env_settings.openai_api_key
        base_url = (row.openai_base_url if row else None) or env_settings.openai_base_url or None
        result = list_models(provider_id, api_key, base_url)
        return {"provider": get_provider(provider_id).label, **result}

    return {"error": f"Unknown tool {name}"}


def chat(db: Session, mailbox: Mailbox, messages: list[dict]) -> dict:
    client, model = llm.get_llm(db)
    convo = [{"role": "system", "content": _system_prompt(db, mailbox)}] + [
        {"role": m["role"], "content": m["content"]} for m in messages
    ]
    actions: list[str] = []
    changed = False

    for _ in range(MAX_ROUNDS):
        resp = client.chat.completions.create(
            model=model, messages=convo, tools=TOOLS, temperature=0.4
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"reply": msg.content or "", "actions": actions, "changed": changed}

        convo.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = _execute(db, mailbox, tc.function.name, args)
            except Exception as exc:
                db.rollback()
                result = {"error": str(exc)[:500]}
            if tc.function.name in WRITE_TOOLS and isinstance(result, dict) and result.get("ok"):
                actions.append(ACTION_LABELS[tc.function.name])
                changed = True
            convo.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    return {
        "reply": "Done — I applied the changes above (I hit my step limit before writing a longer summary).",
        "actions": actions,
        "changed": changed,
    }
