"""Local Ollama backend. Uses Ollama's native structured-output support
(a JSON schema passed via the `format` field) so the model is constrained
to return parseable JSON rather than hoping a prompt instruction works."""
from __future__ import annotations

import json
import logging
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from .base import ExtractionError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    def __init__(self, base_url: str, model: str, embed_model: str = "nomic-embed-text"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model

    def complete(self, system: str, prompt: str, schema: type[T]) -> T:
        return self._complete_with_retry(system, prompt, schema, retries_left=1)

    def _complete_with_retry(self, system: str, prompt: str, schema: type[T], retries_left: int) -> T:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "format": schema.model_json_schema(),
            "stream": False,
            "options": {
                "temperature": 0.0,
                # Caps genuinely runaway generation as a last resort. 2048 was
                # tried first and was wrong — it truncated a legitimately long
                # but valid response (a company with 5 pricing tiers, each with
                # several bullet points, needs more than that). The real fix for
                # the *degenerate* case (open-ended fields ballooning into
                # nonsense) is constraining those fields' schema instead — see
                # MissingField in schemas.py. This cap exists only to bound the
                # worst case, not to constrain normal, valid output.
                "num_predict": 6000,
                # Ollama defaults to a 4096-token context unless told otherwise
                # (confirmed via `ollama ps` during debugging) — raised for
                # headroom, but NOT the fix for the truncation bug (that was
                # num_predict above; see its comment). 16384 measurably slowed
                # generation on this hardware without changing correctness, so
                # this is deliberately a smaller bump — enough buffer over a
                # single page + schema, not enough to make every call slow.
                "num_ctx": 8192,
            },
        }
        try:
            # 300s, not the original 180s: a company with several pricing
            # tiers genuinely needs a long structured response, and testing
            # showed 180s was too tight for that once num_predict was
            # corrected to actually allow the full response through.
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return schema.model_validate(json.loads(content))
        except (ValidationError, json.JSONDecodeError, KeyError) as exc:
            if retries_left > 0:
                logger.warning("Ollama structured output failed validation, retrying once: %s", exc)
                repair_prompt = (
                    f"{prompt}\n\nYour previous response could not be parsed as valid JSON "
                    f"matching the required schema. Error: {exc}. Return ONLY valid JSON matching the schema."
                )
                return self._complete_with_retry(system, repair_prompt, schema, retries_left - 1)
            raise ExtractionError(f"Ollama failed to produce valid {schema.__name__}: {exc}") from exc
        except requests.RequestException as exc:
            raise ExtractionError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
                timeout=60,
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
        return vectors
