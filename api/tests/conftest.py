import pytest
from pydantic import BaseModel

from app.core.provider import GenerationError


class FakeProvider:
    """Stands in for LLMProvider: returns canned payloads per schema name."""

    def __init__(self, payloads: dict[str, object] | None = None) -> None:
        self.payloads = payloads or {}
        self.calls: list[dict[str, object]] = []
        self.fail_for: set[str] = set()

    async def structured(
        self, *, system: str, user: str, schema: type[BaseModel], **kwargs
    ) -> BaseModel:
        self.calls.append({"schema": schema.__name__, "system": system, "user": user, **kwargs})
        if schema.__name__ in self.fail_for:
            raise GenerationError(f"forced failure for {schema.__name__}")
        payload = self.payloads.get(schema.__name__)
        if payload is None:
            raise AssertionError(f"FakeProvider has no payload for {schema.__name__}")
        return schema.model_validate(payload)


@pytest.fixture
def player_payload() -> dict[str, object]:
    return {
        "notes": [
            {"pitch": 60, "start": 0.0, "dur": 0.25, "vel": 100},
            {"pitch": 64, "start": 0.5, "dur": 0.25, "vel": 80},
        ],
        "patch": None,
    }


@pytest.fixture
def cue_payload() -> dict[str, object]:
    return {
        "section": "verse",
        "chords": ["Am7", "Dm7"],
        "energy": 6,
        "density": 5,
        "soloist": "flute",
        "tacet": [],
        "direction": "loose and swung",
    }


@pytest.fixture
def song_plan_payload(cue_payload) -> dict[str, object]:
    return {
        "title": "Monsoon Line",
        "key": "A minor",
        "tempo": 92,
        "time_signature": "4/4",
        "sections": [{**cue_payload, "bars": 2}],
    }
