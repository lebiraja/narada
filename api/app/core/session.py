"""Live jam session state, kept in Redis so any api worker can serve a socket."""

import json
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.schema import Bar, Instrument, SectionCue

SESSION_TTL = 3600
#: The bandleader re-cues on this boundary; players generate every bar.
CUE_EVERY_BARS = 4


class JamSession(BaseModel):
    id: str
    key: str = "A minor"
    tempo: int = Field(default=96, ge=40, le=240)
    next_bar: int = 0
    cue: SectionCue | None = None
    steer: dict[str, Any] = Field(default_factory=dict)
    history: list[Bar] = Field(default_factory=list, max_length=8)

    def remember(self, bar: Bar) -> None:
        """Keep only the recent past — history is prompt context, not an archive."""
        self.history.append(bar)
        self.history = self.history[-4:]

    def needs_new_cue(self) -> bool:
        return self.cue is None or self.next_bar % CUE_EVERY_BARS == 0


class SessionStore:
    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis or Redis.from_url(get_settings().redis_url, decode_responses=True)

    @staticmethod
    def _key(session_id: str) -> str:
        return f"jam:{session_id}"

    async def save(self, session: JamSession) -> None:
        await self._redis.set(self._key(session.id), session.model_dump_json(), ex=SESSION_TTL)

    async def load(self, session_id: str) -> JamSession | None:
        raw = await self._redis.get(self._key(session_id))
        return JamSession.model_validate_json(raw) if raw else None

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))

    async def close(self) -> None:
        await self._redis.aclose()


def apply_steer(session: JamSession, message: dict[str, Any]) -> None:
    """Fold a listener control message into the session's steering state."""
    if (energy := message.get("energy")) is not None:
        session.steer["energy"] = max(1, min(10, int(energy)))
    if (tempo := message.get("tempo")) is not None:
        session.tempo = max(40, min(240, int(tempo)))
    if "mood" in message:
        session.steer["mood"] = str(message["mood"])[:120]
    if "solo" in message:
        solo = message["solo"]
        session.steer["solo"] = Instrument(solo).value if solo else None
    if "drop" in message:
        drop = message["drop"]
        session.steer["drop"] = [Instrument(d).value for d in drop] if drop else []
