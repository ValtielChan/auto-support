<p align="center">
  <img src="docs/logo.png" width="120" alt="Auto Support">
</p>

<h1 align="center">Auto Support</h1>

**Self-hosted AI support agent for your email inboxes.** Connect any existing mailbox over
plain IMAP/SMTP, give it your product context and writing style, and let it read incoming
email, triage it, and answer support requests - automatically or through a human approval
queue. It ships as a single `docker compose up`.

- **Backend** - FastAPI + SQLAlchemy + PostgreSQL, in-process scheduler (APScheduler)
- **Frontend** - React (Vite), served by the backend in production
- **LLM** - OpenAI or any OpenAI-compatible API (Azure, Mistral, OpenRouter, Ollama…)
- **Deploy** - one container for the app + one for PostgreSQL

---

## What it does

- **Live inbox** - a simplified webmail for each mailbox: browse messages, see read/unread,
  render the original HTML (safely, in a sandboxed frame), reply with a small BBCode editor,
  mark read/unread, delete - and next to every message, **what the agent did and why**.
- **AI-assisted replies** - one-click suggestions ("answer", "politely decline", or a custom
  instruction) that draft a full reply using the mailbox's context, playbooks and guidelines.
- **Autonomous agent** - on a schedule it reads unread mail, classifies it (support /
  partnership / marketing / spam / other) and handles each one per your rules: reply, escalate
  to a human, or ignore. Replies are sent automatically or held in an approval queue.
- **Structured configuration** - a general product context, plus **playbooks** (what to do for
  each type of email) and **facts** (product specifics the agent can rely on), long-form
  **documents**, writing style and signature.
- **Configuration copilot** - a chat assistant embedded in each mailbox: describe your product
  in plain language and it writes the context/playbooks/facts and changes any setting for you.
  It can also browse the live mailbox and, on request, mark messages or send replies.
- **Full traceability** - every email, classification, reply and run is stored; each run keeps
  a per-email report (outcome + reason).
- **Safe by default** - credentials encrypted at rest, single admin login, auto-send off until
  you trust the answers, and spam/auto-generated mail is never answered.

---

## Requirements

- **Docker Engine + Docker Compose v2** (`docker compose version` should work). Nothing else -
  no Python or Node needed to run it.
- A mailbox reachable over **IMAP + SMTP**. For Gmail/Outlook, create an **app password**.
- An **LLM API key** (OpenAI or any OpenAI-compatible endpoint). Can be added later in the UI.

---

## Install (plug and play)

```bash
git clone https://github.com/ValtielChan/auto-support.git
cd auto-support

# Creates .env and generates a random SECRET_KEY for you:
./setup.sh

# Open .env and set ADMIN_PASSWORD (and, optionally, OPENAI_API_KEY):
nano .env

# Build and start (app + PostgreSQL):
docker compose up -d --build
```

Then open **http://localhost:8000** and log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

<details>
<summary>Manual setup (without the script)</summary>

```bash
cp .env.example .env
# Edit .env:
#   SECRET_KEY      →  openssl rand -hex 32
#   ADMIN_PASSWORD  →  choose a strong password
#   OPENAI_API_KEY  →  optional (can be set later in the UI)
docker compose up -d --build
```
</details>

That's it - the database schema and the admin account are created automatically on first start.

### First run

1. **Add a mailbox** - from the home screen, *Add mailbox* → enter IMAP/SMTP details →
   *Test connection* → *Save*.
2. **Configure the agent** - open the mailbox, go to **Agent** (product context, model, reply
   language, interval, auto-send, escalation), **Knowledge** (playbooks & facts) and
   **Documents**. Or just tell the **Copilot** about your product and let it fill everything in.
3. **Set the LLM key** - if you didn't set `OPENAI_API_KEY` in `.env`, open the profile menu →
   **Settings** and add your provider / key / model.
4. **Enable & run** - enable the agent on the Agent tab, then *Run agent now*. With auto-send
   off, its replies wait in **Approvals** for you to edit / approve / reject.

---

## Configuration

All configuration is done through the `.env` file (see [`.env.example`](.env.example)).

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | **yes** | Signs auth tokens and encrypts stored credentials. `openssl rand -hex 32`. **Do not change it after first run.** |
| `ADMIN_USERNAME` | yes | Admin login (default `admin`). |
| `ADMIN_PASSWORD` | **yes** | Admin password, created on first startup. |
| `OPENAI_API_KEY` | no | LLM key - can also be set in the UI (Settings). |
| `OPENAI_BASE_URL` | no | For OpenAI-compatible endpoints (Ollama, Mistral, OpenRouter, Azure…). |
| `DEFAULT_MODEL` | no | Default chat model (default `gpt-5.6-terra`). |
| `APP_PORT` | no | Host port (default `8000`). |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | no | Bundled PostgreSQL settings. Change the password for production. |
| `DATABASE_URL` | no | Point at your own PostgreSQL instead of the bundled one. |

---

## Running in production

**Behind a reverse proxy (recommended - terminate TLS there).** The container listens on
`APP_PORT` (default 8000). Example with Caddy:

```
support.example.com {
    reverse_proxy localhost:8000
}
```

**Use your own PostgreSQL.** Set `DATABASE_URL` in `.env` and remove the `db` service from
`docker-compose.yml`. Tables are created automatically on startup.

**Update to a new version.**

```bash
git pull
docker compose up -d --build
```

Your data lives in the `pgdata` Docker volume and survives rebuilds. Additive schema changes
are applied automatically on startup.

**Back up / restore the database.**

```bash
# Backup
docker compose exec db pg_dump -U autosupport autosupport > backup.sql
# Restore
docker compose exec -T db psql -U autosupport autosupport < backup.sql
```

> ⚠ The `pgdata` volume holds all your data. `docker compose down` keeps it; `docker compose
> down -v` **deletes** it. Since credentials are encrypted with `SECRET_KEY`, keep that value
> safe - losing it makes stored mailbox passwords unrecoverable.

---

## How the agent works

The scheduler ticks every minute and runs any mailbox whose interval has elapsed
(also triggered by *Run agent now*). A run:

1. **Fetches unread mail** over IMAP (the unread flag is the source of truth). A message that
   is unread is (re)processed even if already seen before; the folder is opened read-only so
   fetching never marks anything read.
2. **Classifies** each message - support / partnership / marketing / spam / other - using your
   product context and playbooks.
3. **Handles it.** Spam is always ignored. Everything else goes to the reply step, which - following
   your playbooks and guidelines - decides to **reply**, **escalate** to a human, or **ignore**.
   Replies are sent immediately (auto-send) or queued for approval.
4. **Marks handled mail read** on the server so it isn't reprocessed, and writes a run report
   (per-email outcome + reason). Errors stay unread and are retried next run.

Auto-generated mail (bounces, auto-replies, bulk) and the mailbox's own address are never
answered.

---

## Development

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt
# Needs a reachable PostgreSQL, e.g.:  docker compose up -d db
uvicorn app.main:app --reload
```

Frontend (the dev server proxies `/api` to localhost:8000):

```bash
cd frontend
npm install
npm run dev
```

A `TestClient`-based end-to-end smoke test:

```bash
cd backend
PYTHONPATH=. DATABASE_URL="sqlite:///./smoke_test.db" python tests/smoke_test.py
```

See [`AGENT.md`](AGENT.md) for architecture, conventions and gotchas.

---

## Security notes

- Always run behind HTTPS (a reverse proxy) in production.
- Mailbox passwords and the API key are encrypted at rest with a key derived from `SECRET_KEY`.
- Start with **auto-send disabled** (the default) and review drafts until you trust the agent.
- Rendered HTML emails run in a sandboxed frame with scripts disabled; remote images do load
  (like any webmail), which can include tracking pixels.

## License

[MIT](LICENSE)
