"""Model access through any OpenAI-compatible endpoint.

Claude, GPT, Groq and local Ollama all work by changing LLM_BASE_URL.
"""

import asyncio
import json
import logging
import re
from typing import TypeVar

from openai import APIError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

#: Reasoning models spend tokens thinking before the JSON. Too low a ceiling
#: truncates mid-object, which some providers reject outright with a 400.
DEFAULT_MAX_TOKENS = 4000

#: How long we are willing to sit out a rate limit before giving up on a bar.
MAX_RETRY_WAIT = 30.0


class GenerationError(RuntimeError):
    """The model did not give us a usable instance of the requested schema.

    Covers transport failures as well as malformed output: to a caller, a
    rate-limited request and a mangled JSON body are the same event — this
    bar did not get written.
    """


class LLMProvider:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "unset",
        )
        self._leader_model = settings.llm_model_leader
        self._player_model = settings.llm_model_player
        self._player_effort = settings.llm_player_effort.strip()
        self._leader_effort = settings.llm_leader_effort.strip()

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        fast: bool = True,
        temperature: float = 0.9,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        attempts: int = 2,
    ) -> T:
        """Ask the model for JSON matching `schema`.

        Retries once by default, because a truncated or malformed response is
        usually transient. Raises GenerationError when every attempt fails.
        """
        model = self._player_model if fast else self._leader_model
        effort = self._player_effort if fast else self._leader_effort
        # Not every OpenAI-compatible provider accepts this; only send it when set.
        extra = {"reasoning_effort": effort} if effort else {}
        last: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    **extra,
                )
                raw = response.choices[0].message.content or ""
                if not raw.strip():
                    raise ValueError("empty response body")
                return schema.model_validate(json.loads(_strip_fence(raw)))
            except (APIError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                last = exc
                log.warning(
                    "%s attempt %d/%d failed: %s", schema.__name__, attempt + 1, attempts, exc
                )
                if attempt + 1 >= attempts:
                    break
                wait = (
                    retry_after(exc)
                    if isinstance(exc, RateLimitError)
                    else 0.4 * (attempt + 1)
                )
                if wait > MAX_RETRY_WAIT:
                    break
                await asyncio.sleep(wait)

        raise GenerationError(f"{schema.__name__} generation failed: {last}") from last


def retry_after(error: Exception, default: float = 5.0) -> float:
    """Seconds to wait, taken from the provider's own advice when it gives any.

    Providers say "try again in 9.6s" either in a Retry-After header or in the
    error text; guessing shorter just burns another request.
    """
    header = getattr(getattr(error, "response", None), "headers", None)
    if header:
        raw = header.get("retry-after")
        if raw:
            try:
                return min(MAX_RETRY_WAIT, float(raw) + 0.5)
            except ValueError:
                pass

    match = re.search(r"try again in ([0-9.]+)\s*s", str(error))
    if match:
        return min(MAX_RETRY_WAIT, float(match.group(1)) + 0.5)
    return default


def _strip_fence(text: str) -> str:
    """Tolerate models that wrap JSON in a markdown fence."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped.split("\n", 1)[1] if "\n" in stripped else ""
    return body.rsplit("```", 1)[0].strip()
