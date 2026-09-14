"""MCP instrument server: exposes the band as tools any MCP client can play.

Mount this in Claude Code (or any MCP client) and the model becomes the
bandleader directly — writing bars, designing patches, driving the transport.
State lives in Redis alongside live jam sessions, so a bar written here plays
in the browser.
"""

import json

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from app.agents.orchestrator import BandOrchestrator
from app.core.articulation import allowed, describe_voices
from app.core.kit import Kit, describe_kit
from app.core.schema import Bar, BarPart, Instrument, Note, Patch, SectionCue
from app.core.theory import describe_harmony
from app.core.session import JamSession, SessionStore


def _explain(exc: Exception) -> str:
    """A short reason a calling agent can act on, not a Pydantic traceback."""
    if isinstance(exc, ValidationError):
        problems = [
            f"{'.'.join(str(p) for p in err['loc']) or 'value'}: {err['msg']}"
            for err in exc.errors()[:3]
        ]
        return "; ".join(problems)
    return str(exc)

mcp = FastMCP("narada")
MCP_SESSION = "mcp"

_store: SessionStore | None = None
_orchestrator: BandOrchestrator | None = None


def configure(store: SessionStore, orchestrator: BandOrchestrator | None = None) -> None:
    """Inject the backing store and band. Called at startup, and by tests."""
    global _store, _orchestrator
    _store = store
    _orchestrator = orchestrator


def get_store() -> SessionStore:
    """Connect lazily so importing this module never opens a socket."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def get_orchestrator() -> BandOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = BandOrchestrator()
    return _orchestrator


async def _session() -> JamSession:
    store = get_store()
    session = await store.load(MCP_SESSION)
    if session is None:
        session = JamSession(id=MCP_SESSION)
        await store.save(session)
    return session


@mcp.tool()
async def band_state() -> str:
    """Current key, tempo, bar position and what the band last played."""
    session = await _session()
    return json.dumps(
        {
            "key": session.key,
            "tempo": session.tempo,
            "next_bar": session.next_bar,
            "cue": session.cue.model_dump(mode="json") if session.cue else None,
            "recent_bars": [bar.model_dump(mode="json") for bar in session.history],
        }
    )


@mcp.tool()
async def band_set_tempo(tempo: int, key: str | None = None) -> str:
    """Set the band's tempo in BPM (40-240) and optionally the key."""
    session = await _session()
    session.tempo = max(40, min(240, tempo))
    if key:
        session.key = key[:16]
    await get_store().save(session)
    return f"tempo {session.tempo} bpm, key {session.key}"


@mcp.tool()
async def play_bar(
    instrument: str,
    notes: list[dict],
    bar: int | None = None,
    chord: str | None = None,
) -> str:
    """Write one bar for one instrument.

    Args:
        instrument: drums, keys, guitar, flute or violin.
        notes: for melodic instruments,
            [{"pitch": 0-127, "start": 0.0-0.999, "dur": bars, "vel": 1-127,
              "articulation": optional, "slur": optional}]
            For drums, name the kit piece instead of a pitch:
            [{"piece": "kick", "start": 0.0, "dur": 0.1, "vel": optional}]
            start is a fraction of the bar (0.0 is the downbeat, 0.5 halfway)
            and dur is measured in bars (0.25 is one beat in 4/4).
            Call `band_reference` to see the kit pieces and articulations.
        bar: bar index; defaults to the band's current position.
        chord: harmony for this bar, e.g. "Am9". Worth setting — the AI
            players read it when they fill in around you.
    """
    try:
        target = Instrument(instrument)
        parsed = [Note.model_validate(n) for n in notes]
    except ValidationError as exc:
        return (
            f"rejected: {_explain(exc)}. "
            "start is a fraction of the bar (0.0-0.999) and dur is in bars "
            "(0.25 = one beat in 4/4)."
        )
    except ValueError:
        known = ", ".join(i.value for i in Instrument)
        return f"rejected: unknown instrument {instrument!r}. The band is: {known}"

    session = await _session()
    index = session.next_bar if bar is None else bar
    part = BarPart(instrument=target, bar=index, notes=parsed)

    existing = next((b for b in session.history if b.index == index), None)
    if existing:
        existing.parts[target] = part
        if chord:
            existing.chord = chord
    else:
        session.remember(Bar(index=index, chord=chord or "N.C.", parts={target: part}))
        session.next_bar = max(session.next_bar, index + 1)
    await get_store().save(session)

    dropped = len(parsed) - len(part.notes)
    suffix = f" ({dropped} out-of-range notes dropped)" if dropped else ""
    return f"{target.value} bar {index}: {len(part.notes)} notes{suffix}"


@mcp.tool()
async def set_patch(instrument: str, patch: dict) -> str:
    """Design an instrument's synth voice.

    Args:
        instrument: drums, keys, guitar, flute or violin.
        patch: {"oscillator": "sine|square|sawtooth|triangle|fmsine|amsine",
                "attack": s, "decay": s, "sustain": 0-1, "release": s,
                "filter_freq": Hz, "filter_q": 0.1-20, "reverb": 0-1, "delay": 0-1}
    """
    try:
        target = Instrument(instrument)
        validated = Patch.model_validate(patch)
    except ValidationError as exc:
        return f"rejected: {_explain(exc)}"
    except ValueError:
        known = ", ".join(i.value for i in Instrument)
        return f"rejected: unknown instrument {instrument!r}. The band is: {known}"

    session = await _session()
    session.steer.setdefault("patches", {})[target.value] = validated.model_dump()
    await get_store().save(session)
    return f"{target.value} voice set to {validated.oscillator}"


@mcp.tool()
async def band_play(direction: str, bars: int = 4, chords: list[str] | None = None) -> str:
    """Hand the direction to the AI players and let the band write the bars themselves.

    Args:
        direction: what you want, in musician language.
        bars: how many bars to generate (1-16).
        chords: optional progression; the band picks one if omitted.
    """
    session = await _session()
    orchestrator = get_orchestrator()
    cue = SectionCue(chords=chords or ["Am7", "Dm7", "G7", "Cmaj7"], direction=direction[:280])

    for _ in range(max(1, min(16, bars))):
        played = await orchestrator.play_bar(
            bar_index=session.next_bar, cue=cue, history=session.history
        )
        session.remember(played)
        session.next_bar += 1

    await get_store().save(session)
    return f"band played {bars} bars through bar {session.next_bar - 1}"


@mcp.tool()
async def band_reference(instrument: str | None = None, chord: str | None = None) -> str:
    """What an instrument can play: its articulations, kit pieces and the harmony.

    Args:
        instrument: drums, keys, guitar, flute or violin. Omit for all five.
        chord: optional chord symbol, e.g. "Am9" — returns its chord tones,
            scale, colour notes and which notes to avoid landing on.
    """
    if instrument:
        try:
            targets = [Instrument(instrument)]
        except ValueError:
            known = ", ".join(i.value for i in Instrument)
            return f"unknown instrument {instrument!r}. The band is: {known}"
    else:
        targets = list(Instrument)

    sections: list[str] = []
    for target in targets:
        if target is Instrument.DRUMS:
            sections.append(
                f"drums — name a kit piece instead of a pitch:\n{describe_kit()}\n\n"
                f"how to strike them:\n{describe_voices(target)}\n\n"
                f"kits: {', '.join(k.value for k in Kit)}"
            )
        else:
            sections.append(f"{target.value} — articulations:\n{describe_voices(target)}")
        if chord:
            harmony = describe_harmony(chord, target)
            if harmony:
                sections.append(f"  {harmony}")

    return "\n\n".join(sections)


@mcp.tool()
async def band_set_kit(kit: str) -> str:
    """Put the drummer behind a different kit.

    Args:
        kit: standard, room, jazz, brush or orchestra. Brushes suit a ballad;
            jazz is lighter and ride-forward; room has more ambience.
    """
    try:
        chosen = Kit(kit.strip().lower())
    except ValueError:
        return f"rejected: unknown kit {kit!r}. Available: {', '.join(k.value for k in Kit)}"

    session = await _session()
    session.steer["kit"] = chosen.value
    await get_store().save(session)
    return f"drummer is on the {chosen.value} kit"


@mcp.tool()
async def band_reset() -> str:
    """Clear the band's state and start from bar 0."""
    await get_store().delete(MCP_SESSION)
    return "band reset"


if __name__ == "__main__":
    mcp.run()
