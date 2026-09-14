"""Runs the band: one cue, five players in parallel, bar after bar."""

import asyncio

from app.agents.bandleader import Bandleader, SongPlan, chord_for_bar, cue_from_plan, resolve_soloist
from app.agents.instrument import InstrumentAgent
from app.core.config import get_settings
from app.core.provider import LLMProvider
from app.core.schema import BAND, Bar, BarPart, Instrument, Patch, SectionCue, Song

#: Bars of context each player sees. Two is enough to continue an idea
#: without paying for a whole song's history every bar.
HISTORY_BARS = 2


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

    async def play_bar(self, *, bar_index: int, cue: SectionCue, history: list[Bar]) -> Bar:
        """All five players write the same bar at once."""
        chord = chord_for_bar(cue, bar_index)
        cue = cue.model_copy(update={"soloist": resolve_soloist(cue)})
        context = history[-HISTORY_BARS:]

        async def play(player: InstrumentAgent) -> BarPart:
            async with self._gate:
                return await player.play(
                    bar_index=bar_index, cue=cue, history=context, chord=chord
                )

        parts = await asyncio.gather(*(play(player) for player in self.players.values()))
        return Bar(index=bar_index, chord=chord, parts={part.instrument: part for part in parts})

    async def compose(self, brief: str) -> Song:
        """Plan a piece, then play every bar of it."""
        plan: SongPlan = await self.leader.plan_song(brief)
        song = Song(
            title=plan.title,
            key=plan.key,
            tempo=plan.tempo,
            time_signature=plan.time_signature,
            kit=plan.kit,
        )

        bar_index = 0
        for section in plan.sections:
            cue = cue_from_plan(section)
            for offset in range(section.bars):
                bar = await self.play_bar(bar_index=bar_index, cue=cue, history=song.bars)
                _collect_patches(song, bar)
                song.bars.append(bar)
                bar_index += 1

        return song


def _collect_patches(song: Song, bar: Bar) -> None:
    """Hoist any agent-authored patch onto the song so the client applies it once."""
    for instrument, part in bar.parts.items():
        if isinstance(part.patch, Patch):
            song.patches[instrument] = part.patch
