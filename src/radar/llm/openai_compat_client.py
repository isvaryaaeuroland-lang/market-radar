"""Backend for any OpenAI-compatible hosted endpoint (Groq, Together,
OpenRouter, Fireworks, ...) serving an open-source model. Same interface
as OllamaClient — this is the "swap in for the polished demo" path."""
from __future__ import annotations

import json
import logging
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .base import ExtractionError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, embed_model: str | None = None):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.embed_model = embed_model or model

    def complete(self, system: str, prompt: str, schema: type[T]) -> T:
        return self._complete_with_retry(system, prompt, schema, retries_left=1)

    def _complete_with_retry(self, system: str, prompt: str, schema: type[T], retries_left: int) -> T:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=6000,  # see OllamaClient for why this cap exists and why it's this size
            )
            content = resp.choices[0].message.content
            return schema.model_validate(json.loads(content))
        except (ValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
            if retries_left > 0:
                logger.warning("OpenAI-compat structured output failed validation, retrying once: %s", exc)
                repair_prompt = (
                    f"{prompt}\n\nYour previous response could not be parsed as valid JSON "
                    f"matching the required schema. Error: {exc}. Return ONLY valid JSON matching the schema."
                )
                return self._complete_with_retry(system, repair_prompt, schema, retries_left - 1)
            raise ExtractionError(f"Provider failed to produce valid {schema.__name__}: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.embed_model, input=texts)
        return [item.embedding for item in resp.data]
