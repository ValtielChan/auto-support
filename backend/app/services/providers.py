"""LLM provider registry.

Each provider describes how to reach an API and which chat models it offers.
Today both entries speak the OpenAI wire protocol; a future provider with a
different API (e.g. Anthropic) plugs in here with its own `build_client` /
`list_models` behavior, and the rest of the app stays untouched.
"""

from dataclasses import dataclass, field

from openai import OpenAI


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    # Shown in the UI when the provider needs a base URL (self-hosted, etc.).
    needs_base_url: bool = False
    # Maintained list of chat-capable models (newest first). Empty = rely on
    # the live /models endpoint only.
    curated_models: list[str] = field(default_factory=list)
    default_model: str = ""


# Curated OpenAI list — chat-capable API models as of July 2026.
# GPT-5.6 family (Sol/Terra/Luna) is current; 5.5 and 5.4 remain available.
OPENAI_MODELS = [
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.5",
    "gpt-5.5-pro",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o-mini",
]

PROVIDERS: dict[str, Provider] = {
    "openai": Provider(
        id="openai",
        label="OpenAI",
        needs_base_url=False,
        curated_models=OPENAI_MODELS,
        default_model="gpt-5.6-terra",
    ),
    "openai-compatible": Provider(
        id="openai-compatible",
        label="OpenAI-compatible (Ollama, Mistral, OpenRouter…)",
        needs_base_url=True,
        curated_models=[],
        default_model="",
    ),
}


def get_provider(provider_id: str) -> Provider:
    return PROVIDERS.get(provider_id) or PROVIDERS["openai"]


OPENAI_API_URL = "https://api.openai.com/v1"


def build_client(provider_id: str, api_key: str, base_url: str | None) -> OpenAI:
    """Both current providers use the OpenAI SDK; a non-OpenAI-protocol
    provider would return its own client wrapper here.

    Always pass an explicit base_url: with None the SDK falls back to the
    OPENAI_BASE_URL env var, which docker-compose sets to "" — an invalid URL.
    """
    if provider_id == "openai":
        base_url = None  # official endpoint, always
    return OpenAI(api_key=api_key or "not-needed", base_url=base_url or OPENAI_API_URL)


def list_models(provider_id: str, api_key: str, base_url: str | None) -> dict:
    """Return {"models": [...], "source": "curated" | "live" | "none"}.

    The official OpenAI /models endpoint mixes in dozens of non-chat models
    (embeddings, TTS, image...), so for the `openai` provider the curated
    list is authoritative. Compatible endpoints (Ollama & co) usually serve
    exactly their usable models, so there we query live.
    """
    provider = get_provider(provider_id)
    if provider.curated_models:
        return {"models": provider.curated_models, "source": "curated"}
    if not base_url:
        return {"models": [], "source": "none"}
    try:
        client = build_client(provider_id, api_key, base_url)
        models = sorted(m.id for m in client.models.list())
        return {"models": models, "source": "live"}
    except Exception:
        return {"models": [], "source": "none"}
