"""Render a Song to MP3 through fluidsynth and ffmpeg, matching the soundfont mix."""

import asyncio
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.core.midi import song_to_midi
from app.core.schema import Song

RENDER_TIMEOUT_SECONDS = 120
SAMPLE_RATE = 44100


class RenderError(Exception):
    """The audio toolchain is missing, failed, or took too long."""


async def _run(*argv: str) -> None:
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError as exc:
        raise RenderError(f"{argv[0]} is not installed") from exc
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), RENDER_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RenderError(f"{argv[0]} timed out after {RENDER_TIMEOUT_SECONDS}s") from exc
    if process.returncode != 0:
        detail = stderr.decode(errors="replace").strip()[-500:]
        raise RenderError(f"{argv[0]} exited with {process.returncode}: {detail}")


async def render_mp3(song: Song) -> bytes:
    """The song as a loudness-normalised 192 kbps MP3."""
    soundfont = get_settings().soundfont_path
    if not Path(soundfont).is_file():
        raise RenderError(f"soundfont not found at {soundfont}")
    with tempfile.TemporaryDirectory() as workdir:
        midi_path, wav_path, mp3_path = (Path(workdir) / n for n in ("in.mid", "out.wav", "out.mp3"))
        song_to_midi(song).save(midi_path)
        await _run(
            "fluidsynth", "-ni", "-F", str(wav_path), "-r", str(SAMPLE_RATE), soundfont, str(midi_path)
        )
        await _run(
            "ffmpeg", "-nostdin", "-y", "-i", str(wav_path),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-b:a", "192k", str(mp3_path),
        )
        return mp3_path.read_bytes()
