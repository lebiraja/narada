"""The player agent: one instrument, one bar at a time."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agents.prompts import player_system
from app.core.provider import GenerationError, LLMProvider
from app.core.schema import BAND, Bar, BarPart, Instrument, Note, Patch, SectionCue, salvage_notes


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
            return BarPart(instrument=self.instrument, bar=bar_index, notes=[])

        return BarPart(
            instrument=self.instrument,
            bar=bar_index,
            notes=output.notes,
            patch=output.patch,
        )

    def _build_prompt(
        self, *, bar_index: int, cue: SectionCue, history: list[Bar], chord: str
    ) -> str:
        featured = (
            "You have the solo — lead the band."
            if cue.soloist == self.instrument
            else f"{cue.soloist} is soloing; support them and stay out of the way."
            if cue.soloist
            else "No soloist this section; play your normal role."
        )
        return "\n".join(
            [
                f"Bar {bar_index} of the {cue.section}. Chord: {chord}.",
                f"Energy {cue.energy}/10, density {cue.density}/10.",
                f"Bandleader says: {cue.direction or 'play it straight'}",
                featured,
                "",
                "Recent bars:",
                _render_history(history),
                "",
                f"Write bar {bar_index} for {self.instrument}.",
            ]
        )


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
