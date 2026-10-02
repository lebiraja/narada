"""Access and cost limits: key gate, per-IP counters, jam set cap."""

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.agents.orchestrator import BandOrchestrator
from app.core.config import get_settings
from app.core.limits import limits
from app.main import app
from app.ws import jam
from tests.conftest import FakeProvider, FakeStore


@pytest.fixture
def settings(monkeypatch):
    return get_settings()


def test_rest_needs_the_key_when_one_is_set(monkeypatch, settings):
    monkeypatch.setattr(settings, "api_key", "sesame")
    client = TestClient(app)

    assert client.post("/api/export/midi", json={}).status_code == 401
    assert client.post("/api/export/midi", json={}, headers={"X-API-Key": "sesame"}).status_code == 422
    assert client.get("/health").status_code == 200


def test_sockets_need_the_key_when_one_is_set(monkeypatch, settings):
    monkeypatch.setattr(settings, "api_key", "sesame")

    with TestClient(app).websocket_connect("/ws/compose") as socket:
        assert socket.receive_json()["detail"] == "Missing or wrong API key."


def test_compose_is_limited_per_hour(monkeypatch, settings, offline):
    monkeypatch.setattr(settings, "compose_per_hour", 1)
    offline.values["compose:testclient"] = 1

    response = TestClient(app).post("/api/compose", json={"brief": "something rainy"})

    assert response.status_code == 429
    assert offline.ttls == {}  # only the first hit sets the window


def test_too_many_sockets_are_turned_away(monkeypatch, settings, offline):
    offline.values["sockets:testclient"] = settings.max_sockets_per_ip

    with TestClient(app).websocket_connect("/ws/compose") as socket:
        assert socket.receive_json()["detail"] == "Too many open connections."
    assert offline.values["sockets:testclient"] == settings.max_sockets_per_ip


async def test_counters_fail_open_when_redis_is_down(monkeypatch):
    async def down(_key):
        raise RedisConnectionError("gone")

    monkeypatch.setattr(limits._redis, "incr", down)

    assert await limits.hit("anything", 1, 60)


def test_a_jam_stops_at_the_set_limit(monkeypatch, settings, cue_payload, player_payload):
    monkeypatch.setattr(settings, "jam_max_bars", 2)
    provider = FakeProvider({"SectionCue": cue_payload, "PlayerOutput": player_payload})
    monkeypatch.setattr(jam, "make_store", FakeStore)
    monkeypatch.setattr(jam, "make_orchestrator", lambda _provider: BandOrchestrator(provider))

    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        bars = [m for m in (socket.receive_json() for _ in range(3)) if m["type"] == "bar"]
        socket.send_json({"type": "need_bars", "from_bar": 2})
        error = socket.receive_json()

    assert len(bars) == 2
    assert error == {"type": "error", "detail": "Set limit reached"}
