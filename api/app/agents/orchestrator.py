"""Runs the band: one cue, the rhythm section first, then the melody over it."""

import asyncio
from collections.abc import AsyncIterator

from app.agents.bandleader import Bandleader, SongPlan, chord_for_bar, cue_from_plan, resolve_soloist
from app.agents.instrument import InstrumentAgent
from app.core.conductor import conduct
from app.core.config import get_settings
from app.core.provider import LLMProvider
from app.core.schema import BAND, Bar, BarPart, Feel, Instrument, Patch, SectionCue, Song

#: Bars of context each player sees: enough to hear a phrase, not a song.
HISTORY_BARS = 4

#: Layer A plays first, bound to the brief; Layer B hears Layer A's bar.
RHYTHM_LAYER: tuple[Instrument, ...] = (
    Instrument.DRUMS, Instrument.BASS, Instrument.KEYS, Instrument.GUITAR
)
MELODY_LAYER: tuple[Instrument, ...] = (Instrument.FLUTE, Instrument.VIOLIN)


class BandOrchestrator:
    def __init__(
        self, provider: LLMProvider | None = None, max_concurrency: int | None = None
    ) -> None:
        self._provider = provider or LLMProvider()
        self.leader = Bandleader(self._provider)
        self.players: dict[Instrument, InstrumentAgent] = {
            instrument: InstrumentAgent(instrument, self._provider) for instrument in BAND
        }
        limit = max_concurrency or get_settings().llm_max_concurrency
        self._gate = asyncio.Semaphore(max(1, limit))

    async def play_bar(
        self,
        *,
        bar_index: int,
        cue: SectionCue,
        history: list[Bar],
        feel: Feel = Feel(),
        position: tuple[int, int] | None = None,
    ) -> Bar:
        """The rhythm section writes the bar, then the melody plays over it.

        `position` is (bar within the section, bars in the section) when known.
        """
        chord = chord_for_bar(cue, bar_index)
        cue = cue.model_copy(update={"soloist": resolve_soloist(cue)})
        context = history[-HISTORY_BARS:]

        async def play(instrument: Instrument, current: Bar | None) -> BarPart:
            async with self._gate:
                return await self.players[instrument].play(
                    bar_index=bar_index,
                    cue=cue,
                    history=context,
                    chord=chord,
                    feel=feel,
                    position=position,
                    current=current,
                )

        rhythm = await asyncio.gather(*(play(i, None) for i in RHYTHM_LAYER))
        bar = Bar(index=bar_index, chord=chord, parts={part.instrument: part for part in rhythm})
        melody = await asyncio.gather(*(play(i, bar) for i in MELODY_LAYER))
        bar.parts.update({part.instrument: part for part in melody})
        return conduct(bar, feel=feel, previous=history[-1] if history else None, cue=cue)

    async def compose(self, brief: str) -> Song:
        """Plan a piece, then play every bar of it."""
        stream = self.compose_stream(brief)
        plan = await anext(stream)
        assert isinstance(plan, SongPlan)
        song = Song(
            title=plan.title,
            key=plan.key,
            tempo=plan.tempo,
            time_signature=plan.time_signature,
            kit=plan.kit,
        )
        async for bar in stream:
            assert isinstance(bar, Bar)
            _collect_patches(song, bar)
            song.bars.append(bar)
        return song

    async def compose_stream(self, brief: str) -> AsyncIterator[SongPlan | Bar]:
        """Plan a piece, yield the plan, then yield each bar as it is played."""
        plan: SongPlan = await self.leader.plan_song(brief)
        yield plan
        feel = Feel(key=plan.key, tempo=plan.tempo, time_signature=plan.time_signature)

        history: list[Bar] = []
        bar_index = 0
        for section in plan.sections:
            cue = cue_from_plan(section)
            for offset in range(section.bars):
                bar = await self.play_bar(
                    bar_index=bar_index,
                    cue=cue,
                    history=history,
                    feel=feel,
                    position=(offset, section.bars),
                )
                history.append(bar)
                yield bar
                bar_index += 1


def _collect_patches(song: Song, bar: Bar) -> None:
    """Hoist any agent-authored patch onto the song so the client applies it once."""
    for instrument, part in bar.parts.items():
        if isinstance(part.patch, Patch):
            song.patches[instrument] = part.patch
