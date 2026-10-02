import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.orchestrator import BandOrchestrator
from app.core.limits import compose_quota
from app.core.provider import GenerationError, LLMProvider, get_provider
from app.core.schema import Song

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["compose"])


class ComposeRequest(BaseModel):
    brief: str = Field(min_length=3, max_length=600)


@router.post("/compose", response_model=Song, dependencies=[Depends(compose_quota)])
async def compose(request: ComposeRequest, provider: LLMProvider = Depends(get_provider)) -> Song:
    try:
        return await BandOrchestrator(provider).compose(request.brief)
    except GenerationError as exc:
        log.exception("compose failed")
        raise HTTPException(status_code=502, detail="The band could not plan that.") from exc
