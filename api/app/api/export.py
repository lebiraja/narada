from fastapi import APIRouter, Response

from app.core.midi import _slug, stems_zip
from app.core.schema import Song

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export/midi")
async def export_midi(song: Song) -> Response:
    """Five MIDI stems, zipped, built from the same JSON the browser played."""
    return Response(
        content=stems_zip(song),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_slug(song.title)}-stems.zip"'},
    )
