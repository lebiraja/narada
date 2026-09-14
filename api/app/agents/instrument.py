"""The player agent: one instrument, one bar at a time."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agents.prompts import player_system
from app.core.provider import GenerationError, LLMProvider
from app.core.schema import BAND, Bar, BarPart, Instrument, Note, Patch, SectionCue, salvage_notes
from app.core.theory import describe_harmony


class PlayerOutput(BaseModel):
    notes: list[Note] = Field(default_factory=list, max_length=64)
    patch: Patch | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def _salvage(cls, value: Any) -> Any:
        """One misplaced note should cost that note, not the whole bar."""
        return salvage_notes(value) if isinstance(value, list) else value

    @field_validator("patch", mode="before")
    @classmethod
    def _drop_bad_patch(cls, value: Any) -> Any:
        """A malformed patch is not worth losing the notes over."""
        if value is None or isinstance(value, (Patch, dict)):
            return value
        return None


class InstrumentAgent:
    def __init__(self, instrument: Instrument, provider: LLMProvider) -> None:
        self.instrument = instrument
        self._provider = provider
        self._system = player_system(instrument)

    async def play(
        self,
        *,
        bar_index: int,
        cue: SectionCue,
        history: list[Bar],
        chord: str,
    ) -> BarPart:
        """Generate this instrument's part for one bar.

        Returns an empty part on generation failure so one bad response never
        stops the band.
        """
        if self.instrument in cue.tacet:
            return BarPart(instrument=self.instrument, bar=bar_index, notes=[])

        prompt = self._build_prompt(bar_index=bar_index, cue=cue, history=history, chord=chord)
        try:
            output = await self._provider.structured(
                system=self._system, user=prompt, schema=PlayerOutput, fast=True
            )
        except GenerationError:
            return self._cover(bar_index, history)

        return BarPart(
            instrument=self.instrument,
            bar=bar_index,
            notes=output.notes,
            patch=output.patch,
        )

    def _cover(self, bar_index: int, history: list[Bar]) -> BarPart:
        """What to play when the model does not answer in time.

        A musician who loses their place covers rather than stops. Sustaining
        instruments hold what they last played, a little quieter; the drummer
        falls back to plain time, because repeating a bar would re-trigger
        whatever fill was in it.
        """
        last = next(
            (
                bar.parts[self.instrument]
                for bar in reversed(history)
                if self.instrument in bar.parts and bar.parts[self.instrument].notes
            ),
            None,
        )
        if last is None:
            return BarPart(instrument=self.instrument, bar=bar_index, notes=[])

        if self.instrument is Instrument.DRUMS:
            return BarPart(instrument=self.instrument, bar=bar_index, notes=_KEEP_TIME)

        held = [
            note.model_copy(
                update={"bar": bar_index, "vel": max(1, round(note.velocity * 0.85))}
            )
            for note in last.notes
        ]
        return BarPart(instrument=self.instrument, bar=bar_index, notes=held)

    def _build_prompt(
        self, *, bar_index: int, cue: SectionCue, history: list[Bar], chord: str
    ) -> str:
        soloing = cue.soloist == self.instrument
        featured = (
            "You have the solo — lead the band."
            if soloing
            else f"{cue.soloist} is soloing; support them and stay out of the way."
            if cue.soloist
            else "No soloist this section; play your normal role."
        )
        harmony = describe_harmony(chord, self.instrument, soloing=soloing)

        lines = [
            f"Bar {bar_index} of the {cue.section}.",
            f"Energy {cue.energy}/10, density {cue.density}/10.",
            f"Bandleader says: {cue.direction or 'play it straight'}",
            featured,
        ]
        if harmony:
            lines += ["", harmony]
        lines += [
            "",
            "Recent bars:",
            _render_history(history),
            "",
            f"Write bar {bar_index} for {self.instrument}.",
        ]
        return "\n".join(lines)


#: Plain time for a drummer who has lost a bar: pulse, backbeat, nothing clever.
_KEEP_TIME: list[Note] = [
    Note(piece="kick", start=0.0, dur=0.1),
    Note(piece="hat_closed", start=0.25, dur=0.06),
    Note(piece="snare", start=0.5, dur=0.1),
    Note(piece="hat_closed", start=0.75, dur=0.06),
]


def _render_history(history: list[Bar]) -> str:
    """Compact, token-cheap view of what everyone just played."""
    if not history:
        return "(none — this is the first bar)"

    lines: list[str] = []
    for bar in history:
        lines.append(f"bar {bar.index} [{bar.chord}]")
        for instrument in BAND:
            part = bar.parts.get(instrument)
            if part is None or not part.notes:
                continue
            notes = " ".join(f"{n.pitch}@{n.start:.2f}/{n.dur:.2f}" for n in part.notes[:16])
            lines.append(f"  {instrument}: {notes}")
    return "\n".join(lines)
