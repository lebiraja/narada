"""The live loop: the browser keeps time, the band generates ahead of it."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.agents.orchestrator import BandOrchestrator
from app.core.config import get_settings
from app.core.limits import admit, limits
from app.core.provider import LLMProvider, get_provider
from app.core.schema import Feel, Instrument, SectionCue
from app.core.session import CUE_EVERY_BARS, JamSession, SessionStore, apply_steer

log = logging.getLogger(__name__)
router = APIRouter()

#: Never generate more than this far ahead of the playhead.
MAX_LOOKAHEAD = 6

#: Swapped in tests; the orchestrator wraps the shared provider.
make_store = SessionStore
make_orchestrator = BandOrchestrator


@router.websocket("/ws/jam")
async def jam(socket: WebSocket, provider: LLMProvider = Depends(get_provider)) -> None:
    ip = await admit(socket)
    if ip is None:
        return
    max_bars = get_settings().jam_max_bars
    store = make_store()
    orchestrator = make_orchestrator(provider)
    session = JamSession(id=str(uuid.uuid4()))
    generating: asyncio.Task[None] | None = None

    await store.save(session)
    await socket.send_json(
        {
            "type": "session",
            "id": session.id,
            "tempo": session.tempo,
            "key": session.key,
            "time_signature": session.time_signature,
        }
    )

    async def generate_through(target_bar: int) -> None:
        """Fill bars up to `target_bar`, streaming each one as it is written."""
        while session.next_bar <= target_bar:
            if session.needs_new_cue():
                session.cue = await orchestrator.leader.next_cue(
                    bar_index=session.next_bar,
                    key=session.key,
                    tempo=session.tempo,
                    time_signature=session.time_signature,
                    previous=session.cue,
                    steer=session.steer,
                )
                await socket.send_json(
                    {"type": "cue", "bar": session.next_bar, "cue": session.cue.model_dump(mode="json")}
                )

            cue = _steered(session.cue, session.steer)
            bar = await orchestrator.play_bar(
                bar_index=session.next_bar,
                cue=cue,
                history=session.history,
                feel=Feel(key=session.key, tempo=session.tempo, time_signature=session.time_signature),
                position=(session.next_bar % CUE_EVERY_BARS, CUE_EVERY_BARS),
            )
            session.remember(bar)
            session.next_bar += 1
            await store.save(session)
            await socket.send_json({"type": "bar", "bar": bar.model_dump(mode="json")})

    async def _guarded(target_bar: int) -> None:
        """A provider failure must reach the client, not die inside a task."""
        try:
            await generate_through(target_bar)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("bar generation failed in session %s", session.id)
            await socket.send_json({"type": "error", "detail": "The band could not finish that."})

    try:
        while True:
            message = await socket.receive_json()
            kind = message.get("type")

            if kind == "need_bars":
                if max_bars and session.next_bar >= max_bars:
                    await socket.send_json({"type": "error", "detail": "Set limit reached"})
                    break
                playhead = int(message.get("from_bar", 0))
                target = playhead + MAX_LOOKAHEAD
                if max_bars:
                    target = min(target, max_bars - 1)
                if generating is None or generating.done():
                    generating = asyncio.create_task(_guarded(target))

            elif kind == "steer":
                apply_steer(session, message)
                await store.save(session)
                await socket.send_json({"type": "steered", "tempo": session.tempo, "steer": session.steer})

            elif kind == "stop":
                break

    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("jam session %s failed", session.id)
    finally:
        if generating and not generating.done():
            generating.cancel()
        await store.delete(session.id)
        await store.close()
        await limits.close_socket(ip)
        if socket.client_state == WebSocketState.CONNECTED:
            await socket.close()


def _steered(cue: SectionCue | None, steer: dict[str, object]) -> SectionCue:
    """Apply the listener's live overrides on top of the bandleader's cue."""
    base = cue or SectionCue(chords=["Am7", "Dm7", "G7", "Cmaj7"])
    update: dict[str, object] = {}

    if (energy := steer.get("energy")) is not None:
        update["energy"] = energy
    if (solo := steer.get("solo")) is not None:
        update["soloist"] = Instrument(solo)
    if (drop := steer.get("drop")):
        update["tacet"] = sorted({*base.tacet, *(Instrument(d) for d in drop)})

    return base.model_copy(update=update) if update else base
