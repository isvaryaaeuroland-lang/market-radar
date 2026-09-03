"""The interface every LLM backend implements. Agent code depends on this
protocol only — never on a specific provider — so swapping Ollama for a
hosted open-source model is a config change, not a code change."""
from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ExtractionError(Exception):
    """Raised when the LLM's output can't be coerced into the requested schema
    even after one retry. Callers should treat this as a hard failure for
    that item, not silently substitute empty data."""


class LLMClient(Protocol):
    def complete(self, system: str, prompt: str, schema: type[T]) -> T:
        """Call the model and parse its response into `schema`. Implementations
        must validate the response and retry once on failure before raising
        ExtractionError."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...
