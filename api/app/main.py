import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import compose, export, songs
from app.core.config import get_settings
from app.core.limits import require_api_key
from app.core.provider import LLMProvider
from app.db import Base, engine
from app.ws import compose as compose_socket
from app.ws import jam

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Alembic replaces create_all once the schema starts changing.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    app.state.provider = LLMProvider()
    yield
    await app.state.provider.close()
    await engine.dispose()


app = FastAPI(title="Narada", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

guarded = [Depends(require_api_key)]
app.include_router(compose.router, dependencies=guarded)
app.include_router(export.router, dependencies=guarded)
app.include_router(songs.router, dependencies=guarded)
app.include_router(jam.router)
app.include_router(compose_socket.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
