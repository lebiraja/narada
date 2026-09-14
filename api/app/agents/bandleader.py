"""The bandleader: harmony, form, and who gets featured."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agents.prompts import BANDLEADER, COMPOSER
from app.core.provider import GenerationError, LLMProvider
from app.core.schema import Instrument, SectionCue


class SectionPlan(SectionCue):
    bars: int = Field(default=4, ge=1, le=16)


class SongPlan(BaseModel):
    title: str = Field(max_length=120)
    key: str = Field(max_length=16)
    tempo: int = Field(ge=40, le=240)
    time_signature: str = Field(default="4/4", max_length=8)
    #: Which drum kit the piece is played on. An unrecognised name falls back
    #: to the standard kit rather than failing the plan.
    kit: str = Field(default="standard", max_length=16)
    sections: list[SectionPlan] = Field(min_length=1, max_length=16)

    @field_validator("kit", mode="before")
    @classmethod
    def _known_kit(cls, value: Any) -> str:
        from app.core.kit import Kit

        try:
            return Kit(str(value).strip().lower()).value
        except ValueError:
            return Kit.STANDARD.value

    @property
    def total_bars(self) -> int:
        return sum(section.bars for section in self.sections)


class Bandleader:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def plan_song(self, brief: str) -> SongPlan:
        """Turn a user brief into a full section-by-section plan."""
        return await self._provider.structured(
            system=COMPOSER,
            user=f"Brief: {brief}",
            schema=SongPlan,
            fast=False,
            max_tokens=6000,
        )

    async def next_cue(
        self,
        *,
        bar_index: int,
        key: str,
        previous: SectionCue | None,
        steer: dict[str, object],
    ) -> SectionCue:
        """Decide the cue for the upcoming live window.

        Falls back to the previous cue (or a safe default) if generation fails,
        so the live loop never stalls on the leader.
        """
        prompt = "\n".join(
            [
                f"The band is at bar {bar_index} in {key}.",
                f"Previous cue: {previous.model_dump_json() if previous else 'none — open the tune'}",
                f"The listener is steering: {steer or 'nothing requested'}",
                "Give the cue for the next window. Keep it moving somewhere.",
            ]
        )
        try:
            return await self._provider.structured(
                system=BANDLEADER, user=prompt, schema=SectionCue, fast=False, max_tokens=3000
            )
        except GenerationError:
            return previous or SectionCue(chords=["Am7", "Dm7", "G7", "Cmaj7"])


def cue_from_plan(section: SectionPlan) -> SectionCue:
    return SectionCue(**section.model_dump(exclude={"bars"}))


def chord_for_bar(cue: SectionCue, offset: int) -> str:
    """Walk the cue's chord list across the section's bars."""
    return cue.chords[offset % len(cue.chords)]


def resolve_soloist(cue: SectionCue) -> Instrument | None:
    """A soloist listed as tacet is a contradiction; the tacet list wins."""
    if cue.soloist and cue.soloist in cue.tacet:
        return None
    return cue.soloist
