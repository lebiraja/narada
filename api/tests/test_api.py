"""HTTP surface: what the browser actually calls."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.agents.orchestrator import BandOrchestrator
from app.api import compose as compose_route
from app.core.provider import GenerationError
from app.main import app
from tests.conftest import FakeProvider


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def band(monkeypatch, song_plan_payload, player_payload):
    """Swap the real orchestrator for one backed by a fake provider."""
    provider = FakeProvider({"SongPlan": song_plan_payload, "PlayerOutput": player_payload})
    monkeypatch.setattr(compose_route, "BandOrchestrator", lambda: BandOrchestrator(provider))
    return provider


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compose_returns_a_playable_song(client, band):
    response = client.post("/api/compose", json={"brief": "something rainy"})

    assert response.status_code == 200
    song = response.json()
    assert song["title"] == "Monsoon Line"
    assert song["tempo"] == 92
    assert len(song["bars"]) == 2
    assert song["bars"][0]["parts"]["keys"]["notes"]


def test_compose_rejects_an_empty_brief(client, band):
    assert client.post("/api/compose", json={"brief": ""}).status_code == 422


def test_compose_rejects_an_overlong_brief(client, band):
    assert client.post("/api/compose", json={"brief": "x" * 601}).status_code == 422


def test_compose_reports_a_bandleader_failure_as_502(client, band):
    band.fail_for = {"SongPlan"}

    response = client.post("/api/compose", json={"brief": "something rainy"})

    assert response.status_code == 502
    assert "could not plan" in response.json()["detail"]


def test_export_returns_five_stems(client):
    song = {
        "title": "Verify Take",
        "key": "A minor",
        "tempo": 92,
        "time_signature": "4/4",
        "patches": {},
        "bars": [
            {
                "index": 0,
                "chord": "Am7",
                "parts": {
                    "keys": {
                        "instrument": "keys",
                        "bar": 0,
                        "notes": [{"pitch": 69, "start": 0.0, "dur": 0.25, "vel": 100}],
                        "patch": None,
                    }
                },
            }
        ],
    }

    response = client.post("/api/export/midi", json=song)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "verify-take-stems.zip" in response.headers["content-disposition"]
    assert len(zipfile.ZipFile(io.BytesIO(response.content)).namelist()) == 5


def test_export_rejects_a_malformed_song(client):
    assert client.post("/api/export/midi", json={"title": "No Tempo"}).status_code == 422


def test_export_handles_a_song_with_no_bars(client):
    song = {
        "title": "Silence",
        "key": "C",
        "tempo": 100,
        "time_signature": "4/4",
        "patches": {},
        "bars": [],
    }

    response = client.post("/api/export/midi", json=song)

    assert response.status_code == 200
    assert len(zipfile.ZipFile(io.BytesIO(response.content)).namelist()) == 5
