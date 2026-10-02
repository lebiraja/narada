from fastapi import APIRouter, HTTPException, Response

from app.core.midi import slug, stems_zip
from app.core.render import RenderError, render_mp3
from app.core.schema import Song

router = APIRouter(prefix="/api", tags=["export"])

MAX_EXPORT_BARS = 128
MAX_EXPORT_NOTES = 20000


def check_size(song: Song) -> None:
    notes = sum(len(part.notes) for bar in song.bars for part in bar.parts.values())
    if len(song.bars) > MAX_EXPORT_BARS or notes > MAX_EXPORT_NOTES:
        raise HTTPException(
            status_code=413,
            detail=f"Song too large to export: limit is {MAX_EXPORT_BARS} bars and {MAX_EXPORT_NOTES} notes.",
        )


@router.post("/export/midi")
async def export_midi(song: Song) -> Response:
    """Five MIDI stems, zipped, built from the same JSON the browser played."""
    check_size(song)
    return Response(
        content=stems_zip(song),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug(song.title)}-stems.zip"'},
    )


@router.post("/export/audio")
async def export_audio(song: Song) -> Response:
    """The full mix rendered through the GM soundfont, as MP3."""
    check_size(song)
    try:
        audio = await render_mp3(song)
    except RenderError as exc:
        raise HTTPException(status_code=503, detail=f"Audio renderer unavailable: {exc}") from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{slug(song.title)}.mp3"'},
    )
