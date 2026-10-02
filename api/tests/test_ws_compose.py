"""Streaming compose: the protocol the browser plays from as bars land."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agents.bandleader import SongPlan
from app.core.schema import Bar
from app.main import app
from app.ws import compose as compose_socket


class FakeBand:
    def __init__(self, plan: dict, bars: int = 2, fail: bool = False, hang: bool = False) -> None:
        self.plan = SongPlan.model_validate(plan)
        self.bars = bars
        self.fail = fail
        self.hang = hang
        self.cancelled = False

    async def compose_stream(self, brief: str):
        yield self.plan
        for index in range(self.bars):
            yield Bar(index=index, chord="Am7")
        if self.fail:
            raise RuntimeError("secret internals")
        if self.hang:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self.cancelled = True
                raise


@pytest.fixture
def band(monkeypatch, song_plan_payload):
    def wire(**kwargs) -> FakeBand:
        fake = FakeBand(song_plan_payload, **kwargs)
        monkeypatch.setattr(compose_socket, "make_orchestrator", lambda _provider: fake)
        return fake

    return wire


def test_streams_plan_then_bars_then_done(band):
    band()

    with TestClient(app).websocket_connect("/ws/compose") as socket:
        socket.send_json({"type": "compose", "brief": "something rainy"})
        messages = [socket.receive_json() for _ in range(4)]

    plan, first, second, done = messages
    assert plan == {
        "type": "plan",
        "title": "Monsoon Line",
        "key": "A minor",
        "tempo": 92,
        "time_signature": "4/4",
        "kit": "standard",
        "total_bars": 2,
    }
    assert [first["bar"]["index"], second["bar"]["index"]] == [0, 1]
    assert done == {"type": "done"}


def test_a_failure_is_generic(band):
    band(fail=True)

    with TestClient(app).websocket_connect("/ws/compose") as socket:
        socket.send_json({"type": "compose", "brief": "something rainy"})
        messages = [socket.receive_json() for _ in range(4)]

    assert messages[-1] == {"type": "error", "detail": "The band could not finish that."}


def test_a_bad_brief_is_refused(band):
    band()

    with TestClient(app).websocket_connect("/ws/compose") as socket:
        socket.send_json({"type": "compose", "brief": "x"})
        error = socket.receive_json()

    assert error["type"] == "error"


def test_disconnect_cancels_generation(band):
    fake = band(bars=0, hang=True)

    with TestClient(app).websocket_connect("/ws/compose") as socket:
        socket.send_json({"type": "compose", "brief": "something rainy"})
        socket.receive_json()

    for _ in range(50):
        if fake.cancelled:
            break
        asyncio.run(asyncio.sleep(0.02))
    assert fake.cancelled
