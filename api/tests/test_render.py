"""Audio export: the fluidsynth + ffmpeg pipeline and its HTTP route."""

import asyncio
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import export as export_route
from app.core import render
from app.core.config import get_settings
from app.core.render import RenderError, render_mp3
from app.core.schema import Bar, BarPart, Instrument, Note, Song
from app.main import app


def tiny_song(bars: int = 2) -> Song:
    return Song(
        title="Tiny Take",
        key="A minor",
        tempo=100,
        bars=[
            Bar(
                index=i,
                chord="Am7",
                parts={
                    Instrument.KEYS: BarPart(
                        instrument=Instrument.KEYS,
                        bar=i,
                        notes=[Note(pitch=69, start=0.0, dur=0.5, vel=100)],
                    ),
                    Instrument.DRUMS: BarPart(
                        instrument=Instrument.DRUMS,
                        bar=i,
                        notes=[Note(pitch=36, start=0.0, dur=0.1, vel=110)],
                    ),
                },
            )
            for i in range(bars)
        ],
    )


class FakeProcess:
    def __init__(self, returncode: int = 0, hang: bool = False) -> None:
        self.returncode = returncode
        self.hang = hang
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self.hang:
            await asyncio.sleep(10)
        return b"", b"boom"

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


@pytest.fixture
def soundfont(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "gm.sf2"
    path.write_bytes(b"sf2")
    monkeypatch.setattr(get_settings(), "soundfont_path", str(path))
    return path


def fake_exec(monkeypatch, process: FakeProcess, calls: list[tuple[str, ...]]) -> None:
    async def create_subprocess_exec(*argv: str, **kwargs) -> FakeProcess:
        calls.append(argv)
        if argv[0] == "ffmpeg":
            Path(argv[-1]).write_bytes(b"ID3fake")
        return process

    monkeypatch.setattr(render.asyncio, "create_subprocess_exec", create_subprocess_exec)


async def test_render_runs_fluidsynth_then_ffmpeg(monkeypatch, soundfont):
    calls: list[tuple[str, ...]] = []
    fake_exec(monkeypatch, FakeProcess(), calls)

    audio = await render_mp3(tiny_song())

    assert audio == b"ID3fake"
    assert [c[0] for c in calls] == ["fluidsynth", "ffmpeg"]
    assert str(soundfont) in calls[0]
    assert "loudnorm=I=-14:TP=-1.5:LRA=11" in calls[1]


async def test_render_raises_on_non_zero_exit(monkeypatch, soundfont):
    fake_exec(monkeypatch, FakeProcess(returncode=1), [])

    with pytest.raises(RenderError, match="fluidsynth exited with 1: boom"):
        await render_mp3(tiny_song())


async def test_render_kills_a_process_that_times_out(monkeypatch, soundfont):
    process = FakeProcess(hang=True)
    fake_exec(monkeypatch, process, [])
    monkeypatch.setattr(render, "RENDER_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(RenderError, match="timed out"):
        await render_mp3(tiny_song())

    assert process.killed


async def test_render_reports_a_missing_binary(monkeypatch, soundfont):
    async def missing(*argv: str, **kwargs) -> FakeProcess:
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(render.asyncio, "create_subprocess_exec", missing)

    with pytest.raises(RenderError, match="fluidsynth is not installed"):
        await render_mp3(tiny_song())


async def test_render_reports_a_missing_soundfont(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "soundfont_path", str(tmp_path / "nope.sf2"))

    with pytest.raises(RenderError, match="soundfont not found"):
        await render_mp3(tiny_song())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_audio_route_returns_mp3(client, monkeypatch):
    async def fake_render(song: Song) -> bytes:
        return b"ID3fake"

    monkeypatch.setattr(export_route, "render_mp3", fake_render)

    response = client.post("/api/export/audio", json=tiny_song().model_dump(mode="json"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert "tiny-take.mp3" in response.headers["content-disposition"]
    assert response.content == b"ID3fake"


def test_audio_route_returns_503_when_renderer_fails(client, monkeypatch):
    async def broken(song: Song) -> bytes:
        raise RenderError("fluidsynth is not installed")

    monkeypatch.setattr(export_route, "render_mp3", broken)

    response = client.post("/api/export/audio", json=tiny_song().model_dump(mode="json"))

    assert response.status_code == 503
    assert "fluidsynth is not installed" in response.json()["detail"]


@pytest.mark.parametrize("route", ["/api/export/audio", "/api/export/midi"])
def test_export_rejects_too_many_bars(client, route):
    song = tiny_song(export_route.MAX_EXPORT_BARS + 1).model_dump(mode="json")

    response = client.post(route, json=song)

    assert response.status_code == 413


@pytest.mark.parametrize("route", ["/api/export/audio", "/api/export/midi"])
def test_export_rejects_too_many_notes(client, route, monkeypatch):
    monkeypatch.setattr(export_route, "MAX_EXPORT_NOTES", 3)

    response = client.post(route, json=tiny_song().model_dump(mode="json"))

    assert response.status_code == 413


@pytest.mark.skipif(
    shutil.which("fluidsynth") is None
    or shutil.which("ffmpeg") is None
    or not Path(get_settings().soundfont_path).exists(),
    reason="fluidsynth, ffmpeg or the GM soundfont is not installed",
)
async def test_render_produces_a_real_mp3():
    audio = await render_mp3(tiny_song())

    assert audio[:3] == b"ID3" or (audio[0] == 0xFF and audio[1] & 0xE0 == 0xE0)
