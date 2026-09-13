"""Model access through any OpenAI-compatible endpoint.

Claude, GPT, Groq and local Ollama all work by changing LLM_BASE_URL.
"""

import json
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class GenerationError(RuntimeError):
    """The model returned something we could not turn into the requested schema."""


class LLMProvider:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "unset",
        )
        self._leader_model = settings.llm_model_leader
        self._player_model = settings.llm_model_player

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        fast: bool = True,
        temperature: float = 0.9,
        max_tokens: int = 1500,
    ) -> T:
        """Ask the model for JSON matching `schema`. Raises GenerationError on failure."""
        response = await self._client.chat.completions.create(
            model=self._player_model if fast else self._leader_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        try:
            return schema.model_validate(json.loads(_strip_fence(raw)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GenerationError(f"{schema.__name__} generation failed: {exc}") from exc


def _strip_fence(text: str) -> str:
    """Tolerate models that wrap JSON in a markdown fence."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped.split("\n", 1)[1] if "\n" in stripped else ""
    return body.rsplit("```", 1)[0].strip()
