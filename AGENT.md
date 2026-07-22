# AGENT.md - project context for AI agents & contributors

Read this before modifying anything. It explains what the project is, how it is built,
the conventions in place, and the traps that already bit us once.

## What this is

**Auto Support** is a self-hosted platform for AI-powered email support. Users connect
existing mailboxes (plain IMAP/SMTP), attach an AI "support agent" to each one
(product context + writing guidelines + behavior rules), and the agent periodically
reads new email, classifies it (`support` / `partnership` / `marketing` / `spam` /
`other`), and answers support requests - either automatically (`auto_send`) or through
a human approval queue. Requests it cannot resolve can be escalated by email to a human
team, with the customer notified. A second, embedded agent (the **configuration
copilot**) lets users configure all of the above by chatting in natural language.

Distributed free on GitHub; must stay trivially deployable: `cp .env.example .env`,
fill 2 variables, `docker compose up -d --build`.

## Stack

| Layer | Tech | Notes |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (sync), Pydantic v2 | No async DB, no Celery - deliberately simple |
| Scheduler | APScheduler `BackgroundScheduler` | One tick/minute, in-process |
| DB | PostgreSQL 16 (prod), SQLite (tests only) | `create_all` + tiny additive migrations |
| Mail | stdlib `imaplib` / `smtplib` | No OAuth in v1 - app passwords for Gmail/Outlook |
| LLM | `openai` SDK via a provider registry | OpenAI official or any OpenAI-compatible endpoint |
| Frontend | React 18 + Vite, plain JSX, react-router v6 | No TypeScript, no state library |
| Fonts/icons | @fontsource (Archivo Black, Space Grotesk), Font Awesome free | All bundled locally - never add CDN calls |
| Deploy | Docker multi-stage (node build → python image serving API + static) | 2 services: `app` + `db` |

## Repository layout

```
backend/app/
  main.py            FastAPI app, bootstrap (create_all + _migrate + admin), SPA serving
  config.py          pydantic-settings, all env vars
  models.py          SQLAlchemy models (User, AppSettings, Mailbox, Agent, Document,
                     Email, Reply, RunLog)
  schemas.py         All Pydantic request/response schemas
  security.py        bcrypt + JWT helpers
  api/               One router per resource; all under /api prefix
  services/
    crypto.py        Fernet encrypt/decrypt (key derived from SECRET_KEY)
    imap_client.py   Fetch/parse mail, connection tests
    smtp_client.py   Send mail, connection tests
    providers.py     LLM provider registry + curated model lists
    llm.py           get_llm(), classify_email(), generate_reply()
    agent_runner.py  The support-agent pipeline + scheduler entry points
    assistant.py     The configuration copilot (tool-calling loop)
    scheduler.py     APScheduler wiring
frontend/src/
  api.js             fetch wrapper + all API calls; token in localStorage
  App.jsx            Routes + auth guard. Brand-centric IA: Home (/) = mailbox grid;
                     /m/:id = Brand shell (TopBar brand switcher + left section sidebar
                     + Copilot); Settings/Design/MailboxForm wrapped in SimpleLayout.
  pages/             Home, Brand, MailboxForm, Settings, DesignSystem, Login
  components/        Section panels rendered inside Brand (InboxTab, AgentTab,
                     KnowledgeTab, DocumentsTab, ApprovalsTab, RunsTab), TopBar,
                     SimpleLayout, AssistantPanel, ModelSelect, ui.jsx (Badge/Alert/
                     Field/Spinner/Modal)
  styles.css         THE design system - all tokens and component classes
Dockerfile           Multi-stage build; STATIC_DIR=/app/static
docker-compose.yml   app + postgres; DATABASE_URL overridable for external DB
```

## How the pieces work

### Support agent pipeline (`agent_runner.py`)
1. Scheduler tick (every 60 s) finds agents where `enabled && mailbox.active` and
   `last_run_at + interval_minutes` elapsed → `run_mailbox()` (also triggered manually
   via `POST /api/mailboxes/{id}/run`, and each run writes a `RunLog` row).
2. IMAP fetch: **the unread flag is the source of truth** - fetch ALL `UNSEEN` mail
   (no UID gate), folder opened **readonly** (BODY.PEEK, so fetching never flips
   `\Seen`). A message already in the DB but still unread is **re-queued** (status →
   `new`, prior classification cleared, stale unsent drafts dropped) and reprocessed;
   the DB row stays as history. After the run, every message that reached a terminal
   state is **marked read on the server** (`imap_client.set_seen`); errors stay unread
   and get retried. Auto-generated mail (Auto-Submitted, Precedence bulk…) and mail
   from the mailbox's own address are stored as `ignored` (anti-loop) and marked read.
3. Each `new` email (including leftovers from previous failed runs): classify (sets
   `category` + `category_reason`, `processed_at`). `spam` is always `ignored`; every
   other category goes to `generate_reply()`, which - guided by the agent's playbooks
   & guidelines - returns `{action: reply|escalate|ignore, body, reason}` (stored as
   `action_reason`). This is how non-support mail (e.g. marketing) can be politely
   declined or ignored per the user's playbooks.
   - ignore: status `ignored` (with the decision `reason`).
   - escalate (only if enabled + escalation_email set): forward original to the team,
     optionally send the LLM-written notice to the customer, status `escalated`.
   - reply: create `Reply`; `auto_send` → SMTP immediately (status `replied`), else
     draft (status `awaiting_approval`) → approval queue in the UI.
4. Per-email try/except: one bad email marks itself `error` and never kills the run.
   Each run stores a per-email `report` (outcome + reason) on the `RunLog`.

Agent guidance is structured: `product_context` (overview) + `guidelines` (writing
style/tone only) + `signature`, plus `KnowledgeItem` rows of kind `playbook`
(per-situation handling) and `fact` (product specifics), plus long-form `Document`s.
All feed the prompts. The live mailbox (browse/read-unread/reply/delete over IMAP)
is exposed under `/api/mailboxes/{id}/inbox` (`services/imap_client.py`), surfaced in
the frontend **Inbox** tab merged with each message's agent verdict.

Email status flow: `new → ignored | awaiting_approval | replied | escalated | error`.
Replies: `draft → sent | rejected`.

### Configuration copilot (`assistant.py`)
Tool-calling loop (max 8 rounds) over `POST /api/mailboxes/{id}/assistant`. The
frontend sends the whole message history each turn; the backend rebuilds the system
prompt (fresh config snapshot) every call. Tools mirror exactly what the UI can do
(agent config, documents, mailbox name/active, recent emails, model list) - **IMAP/SMTP
credentials are deliberately out of its reach; keep it that way.** Write-tools report
`{ok: true}` → collected into `actions[]` + `changed` flag; the frontend bumps a
`refreshKey` to remount the tabs so forms reload.

### LLM provider layer (`providers.py`)
`PROVIDERS` registry: `openai` (official endpoint, **curated** model list - the live
/models endpoint mixes in embeddings/TTS/etc.) and `openai-compatible` (custom
base_url, models fetched **live**). Adding a new API (e.g. Anthropic) = add a registry
entry and give it its own `build_client` / `list_models` behavior; nothing else should
change. The curated `OPENAI_MODELS` list is maintained by hand - check the official
docs when touching it (July 2026: gpt-5.6-sol/terra/luna, gpt-5.5[-pro],
gpt-5.4[-pro|-mini|-nano], gpt-4.1[-mini], gpt-4o-mini).

### Settings resolution order
DB row (`AppSettings`, set in the UI) wins over env vars (`OPENAI_API_KEY`,
`OPENAI_BASE_URL`, `DEFAULT_MODEL`). Per-agent `model` overrides the platform default.
`get_llm(db)` returns **exactly** `(client, model)` - everything unpacks 2 values.

## Hard-earned gotchas - do not re-break these

- **Never create the OpenAI client with `base_url=None`**: the SDK then falls back to
  the `OPENAI_BASE_URL` env var, which docker-compose sets to `""` (empty string ≠
  None) → `APIConnectionError: Connection error.`. `build_client()` always passes an
  explicit URL. Any new provider must do the same.
- **IMAP `UID N:*` always matches at least the last message** even when its UID < N -
  always re-filter `uid > last_seen_uid` after the search.
- **Empty string means "keep"**: mailbox passwords on update, and the API key in
  settings (`"-"` clears it). Don't "fix" this into overwriting with empty values.
- **Changing `SECRET_KEY` invalidates every stored credential** (Fernet key is derived
  from it) - never rotate it silently in upgrade paths.
- **Schema changes need a migration statement**: `create_all` does NOT alter existing
  tables. Add an `ALTER TABLE …` string to `_migrate()` in `main.py` (idempotent:
  wrapped in try/except, one transaction per statement, must work on Postgres; SQLite
  tolerance via the try/except). For anything non-additive, introduce Alembic first.
- **The Docker volume persists across `docker compose down`** - user data survives
  rebuilds. Never `down -v` without explicit user consent.
- The SPA catch-all route in `main.py` must stay LAST and only registers when
  `STATIC_DIR` exists - don't add routes after it, and keep all API routes under `/api`.
- Scheduler: single tick job with `max_instances=1`; interval changes are picked up
  naturally on the next tick. Don't create one APScheduler job per mailbox.
- LLM JSON output: some compatible endpoints reject `response_format=json_object` -
  `_chat_json()` retries without it and `_parse_json()` tolerates fenced/embedded JSON.
  Keep that fallback when touching LLM calls.

## Code conventions

### Backend (Python)
- Sync everywhere: `def` endpoints (FastAPI threadpool), sync SQLAlchemy sessions,
  background work via `BackgroundTasks` / scheduler thread with its own
  `SessionLocal()` (see `run_mailbox_standalone`). Don't introduce async piecemeal.
- Layering: `api/` = HTTP concerns only (validation, status codes); `services/` = all
  business logic. Routers declare `dependencies=[Depends(get_current_user)]` at router
  level - every new router must be auth-protected the same way and registered in the
  loop in `main.py`.
- Error codes in use: 401 auth, 404 missing resource, 422 semantic validation,
  502 upstream failures (SMTP/LLM) with a readable message. Follow that mapping.
- Pydantic v2 style (`ConfigDict(from_attributes=True)`), SQLAlchemy 2 style
  (`Mapped[...]`, `mapped_column`). Timestamps are timezone-aware UTC (`utcnow()` in
  `models.py`).
- Secrets never leave the API: password fields are write-only, the API key is returned
  masked (`…abcd`). Any new secret field must follow the same pattern (encrypt with
  `services.crypto`, mask on read).
- Comments: only for non-obvious constraints (see `imap_client.py`), in English.

### Frontend (React/JSX)
- Plain JavaScript JSX, function components, `useState`/`useEffect` only. All HTTP goes
  through `api.js` (adds the Bearer token, redirects to /login on 401, throws
  `Error(detail)`). Never call `fetch` directly from a component.
- Pattern per page: `data === null` → `<Spinner/>`, error string → `<Alert>`, then
  render. Buttons show busy labels ("Saving…") and are disabled while pending.
- **Design system is law**: only the classes defined in `styles.css`, only the tokens
  in `:root`. Palette is strictly green (`--green*`, primary) + pink (`--pink*`,
  secondary) + neutrals. **No border-radius, no blur shadows, no new colors.** Any new
  component must be added to `pages/DesignSystem.jsx` (the living style guide at
  `/design`).
- Highlight/underline effects: `.hl`, `.hl-pink`, `.ul-green`, `.ul-pink` (they have
  `width: fit-content` so they hug the text on block elements - keep that).
- Icons: Font Awesome solid, `<i className="fa-solid fa-…" />`, `fa-fw` in menus.
  Everything (fonts, icons, JS) is bundled locally - never add a CDN `<link>`.

## Testing & verification workflow

There is no CI yet. The verification loop that has caught every real bug so far:

1. **Smoke test**: `backend/tests/smoke_test.py` - a `TestClient`-based end-to-end
   script. Run it with:
   `cd backend && PYTHONPATH=. .venv/Scripts/python tests/smoke_test.py`
   (needs `pip install httpx` on top of requirements). It runs against SQLite
   (`DATABASE_URL=sqlite:///./smoke_test.db`), triggers the full lifespan
   (bootstrap + scheduler), and asserts: auth (401/login), mailbox CRUD + agent
   auto-creation, documents, settings (key masking, provider fallback), providers/
   models endpoints, `get_llm` unpacking, and that the assistant fails with a clean
   502 *from the provider* (it sets `OPENAI_BASE_URL=""` to replicate the
   docker-compose env - keep that line).
2. **Frontend build**: `npm run build` must pass (it's the only JS type-check we have).
3. **Deploy check**: `docker compose up -d --build`, then hit `/api/health`, and for
   LLM-path changes run a real one-shot call inside the container
   (`docker exec autosupport-app-1 python -c "...get_llm...create(...)"`).
4. **Visual check**: Playwright (MCP) screenshots of /login, /, /design after any CSS
   change. Delete screenshot artifacts afterwards - they don't belong in the repo.

When debugging LLM/SDK errors, print the `__cause__` chain - the OpenAI SDK wraps
root causes in generic messages ("Connection error.").

## Checklist for common changes

**New API endpoint**: schema in `schemas.py` → router in `api/` (auth dependency!) →
register in `main.py` loop → client function in `api.js` → smoke-test assertion.

**New model/agent field**: `models.py` + `ALTER TABLE` in `_migrate()` + `schemas.py`
+ form field in the matching tab/page + add it to the copilot's `AGENT_FIELDS` and
tool schema in `assistant.py` if it's agent config (the copilot must be able to touch
everything the user can).

**New LLM provider**: entry in `PROVIDERS` + provider-specific `build_client` /
`list_models` branches. UI adapts automatically (Settings provider dropdown,
ModelSelect). Explicit base_url, always.

**New UI component**: build it with existing tokens/classes → document it in
`DesignSystem.jsx` → check both a real page and `/design` visually.

**Dependency updates**: frontend deps are pinned loosely (`^`); the Docker build is
the source of truth - if `npm run build` and the image build pass, ship it.

## Environment variables (deploy-time)

`SECRET_KEY` (required, signs JWTs + derives Fernet key), `ADMIN_USERNAME` /
`ADMIN_PASSWORD` (bootstrap admin, created only if no user exists), `DATABASE_URL`
(defaults to bundled Postgres), `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `DEFAULT_MODEL`
(optional, UI settings take precedence), `APP_PORT`. See `.env.example`.
