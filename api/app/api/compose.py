from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.orchestrator import BandOrchestrator
from app.core.provider import GenerationError
from app.core.schema import Song

router = APIRouter(prefix="/api", tags=["compose"])


class ComposeRequest(BaseModel):
    brief: str = Field(min_length=3, max_length=600)


@router.post("/compose", response_model=Song)
async def compose(request: ComposeRequest) -> Song:
    try:
        return await BandOrchestrator().compose(request.brief)
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=f"The band could not plan that: {exc}") from exc
