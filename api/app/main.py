import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import compose, export
from app.ws import jam

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Narada", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(compose.router)
app.include_router(export.router)
app.include_router(jam.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
