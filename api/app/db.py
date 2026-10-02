"""Postgres persistence for finished songs."""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SongRow(Base):
    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(16))
    tempo: Mapped[int]
    time_signature: Mapped[str] = mapped_column(String(8))
    kit: Mapped[str] = mapped_column(String(16))
    #: The full Song as JSON; the columns above are for listing without it.
    song: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
