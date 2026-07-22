import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import (
    agents,
    app_settings,
    assistant,
    auth,
    dashboard,
    emails,
    inbox,
    mailboxes,
    replies,
    runs,
)
from .config import settings
from .database import Base, SessionLocal, engine
from .models import AppSettings, User
from .security import hash_password
from .services import scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autosupport")


def _migrate() -> None:
    """Tiny additive migrations for columns added after the first release."""
    from sqlalchemy import text

    statements = [
        "ALTER TABLE app_settings ADD COLUMN provider VARCHAR(50) NOT NULL DEFAULT 'openai'",
        "ALTER TABLE run_logs ADD COLUMN report TEXT",
        "ALTER TABLE emails ADD COLUMN processed_at TIMESTAMPTZ",
        "ALTER TABLE emails ADD COLUMN action_reason TEXT",
    ]
    for stmt in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass  # column already exists


def bootstrap() -> None:
    """Create tables, the admin account and the settings row on first start."""
    Base.metadata.create_all(bind=engine)
    _migrate()
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
            logger.info("Created admin user %r", settings.admin_username)
        if db.query(AppSettings).count() == 0:
            db.add(AppSettings(default_model=settings.default_model))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Auto Support", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router_module in (auth, mailboxes, agents, inbox, emails, replies, runs, app_settings, dashboard, assistant):
    app.include_router(router_module.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- static frontend (production build) --------------------------------
if settings.static_dir and os.path.isdir(settings.static_dir):
    assets_dir = os.path.join(settings.static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = os.path.normpath(os.path.join(settings.static_dir, path))
        if (
            path
            and candidate.startswith(os.path.abspath(settings.static_dir))
            and os.path.isfile(candidate)
        ):
            return FileResponse(candidate)
        return FileResponse(os.path.join(settings.static_dir, "index.html"))
