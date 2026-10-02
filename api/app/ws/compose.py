"""Streaming compose: the plan first, then each bar the moment it is written."""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, WebSocket
from pydantic import BaseModel, Field, ValidationError
from starlette.websockets import WebSocketState

from app.agents.bandleader import SongPlan
from app.agents.orchestrator import BandOrchestrator
from app.core.limits import admit, limits
from app.core.provider import LLMProvider, get_provider

log = logging.getLogger(__name__)
router = APIRouter()

#: Swapped in tests.
make_orchestrator = BandOrchestrator


class ComposeMessage(BaseModel):
    type: Literal["compose"]
    brief: str = Field(min_length=3, max_length=600)


@router.websocket("/ws/compose")
async def compose(socket: WebSocket, provider: LLMProvider = Depends(get_provider)) -> None:
    ip = await admit(socket)
    if ip is None:
        return
    try:
        try:
            request = ComposeMessage.model_validate(await socket.receive_json())
        except ValidationError:
            await socket.send_json({"type": "error", "detail": "Send a brief of 3 to 600 characters."})
            return
        if not await limits.compose_allowed(ip):
            await socket.send_json({"type": "error", "detail": "Compose limit reached; try again later."})
            return

        stream = asyncio.create_task(_stream(socket, make_orchestrator(provider), request.brief))
        watch = asyncio.create_task(_until_disconnect(socket))
        # A client that leaves stops the band: no paying for bars nobody hears.
        await asyncio.wait({stream, watch}, return_when=asyncio.FIRST_COMPLETED)
        for task in (stream, watch):
            task.cancel()
    finally:
        await limits.close_socket(ip)
        if socket.client_state == WebSocketState.CONNECTED:
            await socket.close()


async def _stream(socket: WebSocket, orchestrator: BandOrchestrator, brief: str) -> None:
    try:
        async for item in orchestrator.compose_stream(brief):
            if isinstance(item, SongPlan):
                await socket.send_json(
                    {
                        "type": "plan",
                        "title": item.title,
                        "key": item.key,
                        "tempo": item.tempo,
                        "time_signature": item.time_signature,
                        "kit": item.kit,
                        "total_bars": sum(section.bars for section in item.sections),
                    }
                )
            else:
                await socket.send_json({"type": "bar", "bar": item.model_dump(mode="json")})
        await socket.send_json({"type": "done"})
    except Exception:
        log.exception("streaming compose failed")
        await socket.send_json({"type": "error", "detail": "The band could not finish that."})


async def _until_disconnect(socket: WebSocket) -> None:
    while (await socket.receive())["type"] != "websocket.disconnect":
        pass
