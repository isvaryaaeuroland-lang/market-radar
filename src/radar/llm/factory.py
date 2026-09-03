from __future__ import annotations

from ..config import settings
from .base import LLMClient
from .ollama_client import OllamaClient
from .openai_compat_client import OpenAICompatClient

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is not None:
        return _client

    if settings.llm_provider == "openai_compat":
        if not (settings.openai_compat_base_url and settings.openai_compat_api_key and settings.openai_compat_model):
            raise RuntimeError(
                "LLM_PROVIDER=openai_compat requires OPENAI_COMPAT_BASE_URL, "
                "OPENAI_COMPAT_API_KEY, and OPENAI_COMPAT_MODEL in .env"
            )
        _client = OpenAICompatClient(
            base_url=settings.openai_compat_base_url,
            api_key=settings.openai_compat_api_key,
            model=settings.openai_compat_model,
        )
    else:
        _client = OllamaClient(base_url=settings.ollama_base_url, model=settings.ollama_model)

    return _client
