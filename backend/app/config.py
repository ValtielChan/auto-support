from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, read from environment variables (or a .env file)."""

    database_url: str = "postgresql+psycopg://autosupport:autosupport@localhost:5432/autosupport"

    # Used to sign JWTs and to derive the encryption key for stored credentials.
    # MUST be overridden in production.
    secret_key: str = "change-me-please"

    # Bootstrap admin account, created on first startup if no user exists.
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Optional LLM defaults; can also be configured from the UI (stored in DB).
    openai_api_key: str = ""
    openai_base_url: str = ""
    default_model: str = "gpt-5.6-terra"

    # Directory containing the built frontend (set in the Docker image).
    static_dir: str = ""

    # How often the scheduler checks whether a mailbox is due (seconds).
    scheduler_tick_seconds: int = 60

    access_token_expire_minutes: int = 60 * 24 * 7

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
