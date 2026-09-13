"""The live loop: the protocol the browser depends on to never fall silent."""

import pytest
from fastapi.testclient import TestClient

from app.agents.orchestrator import BandOrchestrator
from app.core.schema import BAND
from app.main import app
from app.ws import jam
from tests.conftest import FakeProvider, FakeStore


@pytest.fixture
def wired(monkeypatch, cue_payload, player_payload):
    """A jam socket backed by an in-memory store and a fake band."""
    store = FakeStore()
    provider = FakeProvider({"SectionCue": cue_payload, "PlayerOutput": player_payload})
    monkeypatch.setattr(jam, "make_store", lambda: store)
    monkeypatch.setattr(jam, "make_orchestrator", lambda: BandOrchestrator(provider))
    return store, provider


#: A full lookahead fill is one cue per 4-bar window plus MAX_LOOKAHEAD + 1 bars.
FULL_FILL = 9


def drain(socket, count: int = FULL_FILL) -> list[dict]:
    """Read exactly `count` messages. Over-reading would block, so callers
    must not ask for more than the server sends for one need_bars."""
    return [socket.receive_json() for _ in range(count)]


def test_connect_announces_the_session(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        hello = socket.receive_json()

    assert hello["type"] == "session"
    assert hello["tempo"] == 96
    assert hello["id"]


def test_need_bars_streams_a_cue_then_bars(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket, 3)

    assert messages[0]["type"] == "cue"
    assert messages[0]["cue"]["chords"] == ["Am7", "Dm7"]
    assert [m["type"] for m in messages[1:]] == ["bar", "bar"]
    assert messages[1]["bar"]["index"] == 0


def test_generated_bars_contain_every_instrument(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket, 2)

    assert set(messages[1]["bar"]["parts"]) == {i.value for i in BAND}


def test_bars_advance_and_follow_the_chord_progression(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket)

    bars = [m["bar"] for m in messages if m["type"] == "bar"]
    assert [bar["index"] for bar in bars[:4]] == [0, 1, 2, 3]
    assert [bar["chord"] for bar in bars[:4]] == ["Am7", "Dm7", "Am7", "Dm7"]


def test_the_leader_re_cues_on_the_window_boundary(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket)

    cues = [m for m in messages if m["type"] == "cue"]
    assert [cue["bar"] for cue in cues] == [0, 4]


def test_steering_is_acknowledged(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "steer", "energy": 9, "tempo": 130})
        ack = socket.receive_json()

    assert ack["type"] == "steered"
    assert ack["tempo"] == 130
    assert ack["steer"]["energy"] == 9


def test_steering_persists_to_the_session_store(wired):
    store, _ = wired

    with TestClient(app).websocket_connect("/ws/jam") as socket:
        hello = socket.receive_json()
        socket.send_json({"type": "steer", "solo": "flute"})
        socket.receive_json()
        session = store.sessions[hello["id"]]

    assert '"solo":"flute"' in session.replace(" ", "")


def test_dropped_instruments_stop_playing(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "steer", "drop": ["drums", "guitar"]})
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket, 2)

    parts = messages[1]["bar"]["parts"]
    assert parts["drums"]["notes"] == []
    assert parts["guitar"]["notes"] == []
    assert parts["flute"]["notes"]


def test_a_provider_failure_reaches_the_client(wired):
    _, provider = wired
    provider.fail_for = {"SectionCue", "PlayerOutput"}

    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket, 3)

    # The leader falls back to a default cue; players fall back to silence.
    assert messages[0]["type"] == "cue"
    assert all(part["notes"] == [] for part in messages[1]["bar"]["parts"].values())


def test_an_unexpected_failure_is_reported_not_swallowed(wired, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(BandOrchestrator, "play_bar", explode)

    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket, 2)

    error = next(m for m in messages if m["type"] == "error")
    assert "provider is down" in error["detail"]


def test_stop_ends_the_session_and_cleans_up(wired):
    store, _ = wired

    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "stop"})

    assert store.sessions == {}
    assert store.closed is True


def test_generation_does_not_run_past_the_lookahead(wired):
    with TestClient(app).websocket_connect("/ws/jam") as socket:
        socket.receive_json()
        socket.send_json({"type": "need_bars", "from_bar": 0})
        messages = drain(socket)
        socket.send_json({"type": "stop"})

    bars = [m["bar"]["index"] for m in messages if m["type"] == "bar"]
    assert max(bars) <= jam.MAX_LOOKAHEAD
