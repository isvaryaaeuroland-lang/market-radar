"""Central config, loaded once from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M")

    openai_compat_base_url: str = os.getenv("OPENAI_COMPAT_BASE_URL", "")
    openai_compat_api_key: str = os.getenv("OPENAI_COMPAT_API_KEY", "")
    openai_compat_model: str = os.getenv("OPENAI_COMPAT_MODEL", "")

    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")

    data_dir: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()

    def __post_init__(self) -> None:
        (self.data_dir / "snapshots").mkdir(parents=True, exist_ok=True)


settings = Settings()
