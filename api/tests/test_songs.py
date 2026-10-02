"""Saved songs: persistence without a live Postgres."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.export import MAX_EXPORT_BARS
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    """A throwaway SQLite file standing in for Postgres. No pooling: each test
    request runs on its own event loop, and a pooled connection would outlive it."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/songs.db", poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def db():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = db
    yield TestClient(app)
    app.dependency_overrides.clear()


SONG = {
    "title": "Monsoon Line",
    "key": "A minor",
    "tempo": 92,
    "bars": [{"index": 0, "chord": "Am7", "parts": {}}],
}


def test_a_saved_song_comes_back_whole(client):
    saved = client.post("/api/songs", json=SONG)

    assert saved.status_code == 201
    loaded = client.get(f"/api/songs/{saved.json()['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["title"] == "Monsoon Line"
    assert loaded.json()["bars"][0]["chord"] == "Am7"


def test_history_lists_summaries(client):
    client.post("/api/songs", json=SONG)
    client.post("/api/songs", json={**SONG, "title": "Second"})

    listing = client.get("/api/songs").json()

    assert {song["title"] for song in listing} == {"Monsoon Line", "Second"}
    assert set(listing[0]) == {"id", "title", "key", "tempo", "time_signature", "created_at"}


def test_an_unknown_song_is_404(client):
    response = client.get("/api/songs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_an_oversized_song_is_refused(client):
    bars = [{"index": i, "chord": "Am7", "parts": {}} for i in range(MAX_EXPORT_BARS + 1)]

    response = client.post("/api/songs", json={**SONG, "bars": bars})

    assert response.status_code == 413
