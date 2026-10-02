"""The player agent: one instrument, one bar at a time."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agents.bandleader import chord_for_bar
from app.agents.prompts import player_system
from app.core.meter import parse_time_signature, steps_per_bar
from app.core.provider import GenerationError, LLMProvider
from app.core.schema import (
    BAND,
    ArrangementBrief,
    Bar,
    BarPart,
    Feel,
    Instrument,
    Note,
    Patch,
    SectionCue,
    salvage_notes,
)
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


#: Sampling temperature by role: time-keepers tight, melody freer.
_TEMPERATURE: dict[Instrument, float] = {
    Instrument.DRUMS: 0.5,
    Instrument.BASS: 0.5,
    Instrument.KEYS: 0.7,
    Instrument.GUITAR: 0.7,
    Instrument.FLUTE: 0.8,
    Instrument.VIOLIN: 0.8,
}

#: Bars a player may cover in a row before dropping out.
MAX_COVERS = 2


class InstrumentAgent:
    def __init__(self, instrument: Instrument, provider: LLMProvider) -> None:
        self.instrument = instrument
        self._provider = provider
        self._system = player_system(instrument)
        self._covers = 0

    async def play(
        self,
        *,
        bar_index: int,
        cue: SectionCue,
        history: list[Bar],
        chord: str,
        feel: Feel = Feel(),
        position: tuple[int, int] | None = None,
        current: Bar | None = None,
    ) -> BarPart:
        """Generate this instrument's part for one bar.

        `position` is (bar within the section, bars in the section) when the
        caller knows the form. `current` is what the others have already
        written for this same bar. Returns an empty part on generation failure so
        one bad response never stops the band.
        """
        if self.instrument in cue.tacet:
            return BarPart(instrument=self.instrument, bar=bar_index, notes=[])

        steps = steps_per_bar(feel.time_signature)
        prompt = self._build_prompt(
            bar_index=bar_index,
            cue=cue,
            history=history,
            chord=chord,
            feel=feel,
            steps=steps,
            position=position,
            current=current,
        )
        try:
            output = await self._provider.structured(
                system=self._system,
                user=prompt,
                schema=PlayerOutput,
                fast=True,
                temperature=_TEMPERATURE[self.instrument],
            )
        except GenerationError:
            return self._cover(bar_index, history)

        self._covers = 0
        return BarPart(
            instrument=self.instrument,
            bar=bar_index,
            notes=[placed for note in output.notes if (placed := _on_grid(note, steps))],
            patch=output.patch,
        )

    def _cover(self, bar_index: int, history: list[Bar]) -> BarPart:
        """What to play when the model does not answer in time.

        A musician who loses their place covers rather than stops. Sustaining
        instruments hold what they last played, a little quieter; the drummer
        falls back to plain time, because repeating a bar would re-trigger
        whatever fill was in it. After `MAX_COVERS` bars in a row they lay
        out rather than hold one sound forever.
        """
        self._covers += 1
        if self._covers > MAX_COVERS:
            return BarPart(instrument=self.instrument, bar=bar_index, notes=[])

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
        self,
        *,
        bar_index: int,
        cue: SectionCue,
        history: list[Bar],
        chord: str,
        feel: Feel,
        steps: int,
        position: tuple[int, int] | None,
        current: Bar | None,
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

        last_in_section = position is not None and position[0] == position[1] - 1
        next_chord = "(new section)" if last_in_section else chord_for_bar(cue, bar_index + 1)
        grouping = _GROUPINGS.get(parse_time_signature(feel.time_signature))
        meter = (
            f"{feel.time_signature}"
            + (f" at {feel.tempo} bpm" if feel.tempo else "")
            + f" — {steps} steps per bar, 4 steps per quarter-note beat"
            + (f"; counted {grouping}." if grouping else ".")
        )

        lines = [
            f"Bar {bar_index} of the {cue.section}."
            + (f" Bar {position[0] + 1} of {position[1]} in this section." if position else ""),
            *([f"Key: {feel.key}."] if feel.key else []),
            meter,
            f"Chord this bar: {chord}; next bar: {next_chord}.",
            f"Energy {cue.energy}/10, density {cue.density}/10.",
            f"Bandleader says: {cue.direction or 'play it straight'}",
            featured,
        ]
        if harmony:
            lines += ["", harmony]
        if cue.brief:
            lines += ["", "Section plan:", *self._plan_lines(cue.brief, position)]
        if current and current.parts:
            lines += [
                "",
                "Right now the others play (pitch@step/len):",
                _render_history([current], steps),
            ]
        lines += [
            "",
            "Recent bars (pitch@step/len):",
            _render_history(history, steps),
            "",
            f"Steps run 0-{steps - 1}. E.g. step 0 len 4 is a quarter note on the "
            f"downbeat; step {steps - 2} len 2 is the bar's last eighth note.",
            f"Write bar {bar_index} for {self.instrument}.",
        ]
        return "\n".join(lines)

    def _plan_lines(
        self, brief: ArrangementBrief, position: tuple[int, int] | None
    ) -> list[str]:
        """The parts of the section's score that concern this player, this bar."""
        offset = position[0] if position else 0
        lines: list[str] = []
        if self.instrument is Instrument.DRUMS and brief.groove:
            lines.append(
                "Groove: " + "; ".join(f"{piece} {steps}" for piece, steps in brief.groove.items())
            )
        if self.instrument in RHYTHM_PARTS and brief.comp_rhythm:
            lines.append(f"Comp rhythm (stab on steps): {brief.comp_rhythm}")
        if self.instrument is Instrument.BASS and brief.bass_rhythm:
            lines.append(f"Bass rhythm (play on steps): {brief.bass_rhythm}")
        if self.instrument in MELODY_PARTS and brief.motif:
            motif = " ".join(
                f"{n.degree}{'+' * max(0, n.octave_offset)}{'-' * max(0, -n.octave_offset)}"
                f"@{n.step}/{n.len}"
                for n in brief.motif
            )
            lines.append(
                f"Motif (scale degree@step/len): {motif}"
                + (f"; develop it: {brief.motif_development}" if brief.motif_development else "")
            )
        if self.instrument in MELODY_PARTS and brief.call_response:
            turn = next((t for t in brief.call_response if t.bar == offset), None)
            if turn:
                lines.append(
                    "You lead this bar." if turn.lead == self.instrument
                    else f"{turn.lead} leads this bar; answer in its gaps."
                )
        if role := brief.roles.get(self.instrument):
            lines.append(
                f"Your role: {role.band} register"
                + (f", doubling {role.doubles}" if role.doubles else "")
                + (f", enter at bar {role.enters_bar + 1}" if role.enters_bar else "")
                + "."
            )
        if brief.energy_curve:
            energy = brief.energy_curve[min(offset, len(brief.energy_curve) - 1)]
            lines.append(f"Energy this bar: {energy}/10.")
        return lines


#: Who keeps the rhythm-section brief versus who carries the motif.
RHYTHM_PARTS = (Instrument.KEYS, Instrument.GUITAR)
MELODY_PARTS = (Instrument.FLUTE, Instrument.VIOLIN)


#: Plain time for a drummer who has lost a bar: pulse, backbeat, nothing clever.
_KEEP_TIME: list[Note] = [
    Note(piece="kick", start=0.0, dur=0.1),
    Note(piece="hat_closed", start=0.25, dur=0.06),
    Note(piece="snare", start=0.5, dur=0.1),
    Note(piece="hat_closed", start=0.75, dur=0.06),
]


#: How odd meters are felt, keyed by (numerator, denominator).
_GROUPINGS: dict[tuple[int, int], str] = {(7, 8): "3+2+2 eighths", (5, 4): "3+2 beats"}


def _on_grid(note: Note, steps: int) -> Note | None:
    """Place a note written on the step grid; legacy float notes pass through.

    A step past the bar's last one is the next bar's downbeat, so it is
    discarded just as `salvage_notes` discards a start of 1.0.
    """
    if note.step is None:
        return note
    if note.step >= steps:
        return None
    length = min(note.len or 1, 4 * steps)
    return note.model_copy(update={"start": note.step / steps, "dur": length / steps, "len": length})


def _render_history(history: list[Bar], steps: int) -> str:
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
            notes = " ".join(
                f"{n.pitch}@{round(n.start * steps)}/{max(1, round(n.dur * steps))}"
                for n in part.notes[:16]
            )
            lines.append(f"  {instrument}: {notes}")
    return "\n".join(lines)
