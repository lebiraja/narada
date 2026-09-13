"""Shared musical contract: what agents emit, what the browser plays."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Instrument(StrEnum):
    DRUMS = "drums"
    KEYS = "keys"
    GUITAR = "guitar"
    FLUTE = "flute"
    VIOLIN = "violin"


BAND: tuple[Instrument, ...] = tuple(Instrument)

#: Pitch range each instrument can physically play (MIDI note numbers).
RANGES: dict[Instrument, tuple[int, int]] = {
    Instrument.DRUMS: (35, 81),  # GM percussion map
    Instrument.KEYS: (21, 108),
    Instrument.GUITAR: (40, 88),
    Instrument.FLUTE: (60, 96),
    Instrument.VIOLIN: (55, 100),
}


class Note(BaseModel):
    pitch: int = Field(ge=0, le=127)
    start: float = Field(ge=0.0, lt=1.0, description="Position in bar, 0.0-1.0")
    dur: float = Field(gt=0.0, le=4.0, description="Duration in bars")
    vel: int = Field(default=90, ge=1, le=127)


class Patch(BaseModel):
    """Agent-authored synth voice. Validated shape, never executable code."""

    oscillator: Literal["sine", "square", "sawtooth", "triangle", "fmsine", "amsine"]
    attack: float = Field(ge=0.001, le=4.0)
    decay: float = Field(ge=0.001, le=4.0)
    sustain: float = Field(ge=0.0, le=1.0)
    release: float = Field(ge=0.001, le=8.0)
    filter_freq: float = Field(default=8000.0, ge=20.0, le=20000.0)
    filter_q: float = Field(default=1.0, ge=0.1, le=20.0)
    reverb: float = Field(default=0.0, ge=0.0, le=1.0)
    delay: float = Field(default=0.0, ge=0.0, le=1.0)


class BarPart(BaseModel):
    """One instrument's contribution to one bar."""

    instrument: Instrument
    bar: int = Field(ge=0)
    notes: list[Note] = Field(default_factory=list, max_length=64)
    patch: Patch | None = None

    @field_validator("notes")
    @classmethod
    def _notes_in_range(cls, notes: list[Note], info) -> list[Note]:
        instrument = info.data.get("instrument")
        if instrument is None:
            return notes
        lo, hi = RANGES[instrument]
        return [n for n in notes if lo <= n.pitch <= hi]


class Bar(BaseModel):
    """All five parts for a single bar, ready to schedule."""

    index: int = Field(ge=0)
    chord: str = "N.C."
    parts: dict[Instrument, BarPart] = Field(default_factory=dict)


class SectionCue(BaseModel):
    """Bandleader's instruction to the players for the next window."""

    section: str = Field(default="verse", max_length=32)
    chords: list[str] = Field(min_length=1, max_length=16)
    energy: int = Field(default=5, ge=1, le=10)
    density: int = Field(default=5, ge=1, le=10)
    soloist: Instrument | None = None
    tacet: list[Instrument] = Field(default_factory=list, description="Sit this window out")
    direction: str = Field(default="", max_length=280)


class Song(BaseModel):
    title: str = Field(max_length=120)
    key: str = Field(max_length=16)
    tempo: int = Field(ge=40, le=240)
    time_signature: str = Field(default="4/4", max_length=8)
    patches: dict[Instrument, Patch] = Field(default_factory=dict)
    bars: list[Bar] = Field(default_factory=list)
