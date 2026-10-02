import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.export import check_size
from app.core.schema import Song
from app.db import SongRow, get_db

router = APIRouter(prefix="/api", tags=["songs"])

#: How many songs the history list returns, newest first.
HISTORY_LIMIT = 50


class SongSummary(BaseModel):
    id: uuid.UUID
    title: str
    key: str
    tempo: int
    time_signature: str
    created_at: datetime


class SavedSong(BaseModel):
    id: uuid.UUID


@router.post("/songs", response_model=SavedSong, status_code=201)
async def save_song(song: Song, db: AsyncSession = Depends(get_db)) -> SavedSong:
    check_size(song)
    row = SongRow(
        title=song.title,
        key=song.key,
        tempo=song.tempo,
        time_signature=song.time_signature,
        kit=song.kit,
        song=song.model_dump(mode="json"),
    )
    db.add(row)
    await db.commit()
    return SavedSong(id=row.id)


@router.get("/songs", response_model=list[SongSummary])
async def list_songs(db: AsyncSession = Depends(get_db)) -> list[SongSummary]:
    rows = await db.scalars(
        select(SongRow).order_by(SongRow.created_at.desc()).limit(HISTORY_LIMIT)
    )
    return [SongSummary.model_validate(row, from_attributes=True) for row in rows]


@router.get("/songs/{song_id}", response_model=Song)
async def get_song(song_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Song:
    row = await db.get(SongRow, song_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such song.")
    return Song.model_validate(row.song)
