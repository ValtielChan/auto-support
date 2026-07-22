from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings as env_settings
from ..models import AppSettings
from ..schemas import ModelsOut, ProviderOut, SettingsIn, SettingsOut
from ..services import crypto
from ..services.providers import PROVIDERS, get_provider, list_models
from .deps import get_current_user, get_db

router = APIRouter(
    prefix="/api", tags=["settings"], dependencies=[Depends(get_current_user)]
)


def _get_row(db: Session) -> AppSettings:
    row = db.query(AppSettings).first()
    if row is None:
        row = AppSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _effective_key(row: AppSettings) -> str:
    stored = crypto.decrypt(row.openai_api_key_enc) if row.openai_api_key_enc else ""
    return stored or env_settings.openai_api_key


def _to_out(row: AppSettings) -> SettingsOut:
    key = _effective_key(row)
    return SettingsOut(
        provider=row.provider or "openai",
        has_api_key=bool(key),
        api_key_hint=f"…{key[-4:]}" if key else "",
        openai_base_url=row.openai_base_url or "",
        default_model=row.default_model,
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return _to_out(_get_row(db))


@router.put("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    row = _get_row(db)
    provider = get_provider(payload.provider)
    row.provider = provider.id
    if payload.openai_api_key == "-":
        row.openai_api_key_enc = None
    elif payload.openai_api_key:
        row.openai_api_key_enc = crypto.encrypt(payload.openai_api_key)
    row.openai_base_url = payload.openai_base_url.strip() or None
    row.default_model = payload.default_model.strip() or provider.default_model
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("/providers", response_model=list[ProviderOut])
def providers_list():
    return [
        ProviderOut(
            id=p.id,
            label=p.label,
            needs_base_url=p.needs_base_url,
            default_model=p.default_model,
        )
        for p in PROVIDERS.values()
    ]


@router.get("/models", response_model=ModelsOut)
def models_list(db: Session = Depends(get_db)):
    row = _get_row(db)
    provider_id = row.provider or "openai"
    base_url = row.openai_base_url or env_settings.openai_base_url or None
    result = list_models(provider_id, _effective_key(row), base_url)
    return ModelsOut(provider=provider_id, source=result["source"], models=result["models"])
