"""Shared musical contract: what agents emit, what the browser plays."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)


class Instrument(StrEnum):
    DRUMS = "drums"
    BASS = "bass"
    KEYS = "keys"
    GUITAR = "guitar"
    FLUTE = "flute"
    VIOLIN = "violin"

    @classmethod
    def _missing_(cls, value: object) -> "Instrument | None":
        """Models write 'Flute', 'Keyboard', 'Piano'. Accept what they mean."""
        if not isinstance(value, str):
            return None
        return _ALIASES.get(value.strip().lower())


#: Names a model may reasonably use for each player.
_ALIASES: dict[str, Instrument] = {
    "drums": Instrument.DRUMS,
    "drum": Instrument.DRUMS,
    "drumkit": Instrument.DRUMS,
    "drum kit": Instrument.DRUMS,
    "percussion": Instrument.DRUMS,
    "bass": Instrument.BASS,
    "bass guitar": Instrument.BASS,
    "electric bass": Instrument.BASS,
    "double bass": Instrument.BASS,
    "upright": Instrument.BASS,
    "upright bass": Instrument.BASS,
    "bassist": Instrument.BASS,
    "keys": Instrument.KEYS,
    "key": Instrument.KEYS,
    "keyboard": Instrument.KEYS,
    "piano": Instrument.KEYS,
    "rhodes": Instrument.KEYS,
    "guitar": Instrument.GUITAR,
    "acoustic guitar": Instrument.GUITAR,
    "electric guitar": Instrument.GUITAR,
    "gtr": Instrument.GUITAR,
    "flute": Instrument.FLUTE,
    "violin": Instrument.VIOLIN,
    "fiddle": Instrument.VIOLIN,
    "strings": Instrument.VIOLIN,
}


def coerce_instruments(values: Any) -> list["Instrument"]:
    """Map a model's instrument list onto the band, dropping anyone not in it.

    A bandleader that asks the trumpet to sit out is describing a band we do
    not have; that should not invalidate an otherwise good plan.
    """
    if not isinstance(values, list):
        return []
    out: list[Instrument] = []
    for value in values:
        try:
            instrument = Instrument(value)
        except ValueError:
            continue
        if instrument not in out:
            out.append(instrument)
    return out


def coerce_optional_instrument(value: Any) -> "Instrument | None":
    """Same, for a single optional player such as the soloist."""
    if value is None:
        return None
    try:
        return Instrument(value)
    except ValueError:
        return None


BAND: tuple[Instrument, ...] = tuple(Instrument)

#: Pitch range each instrument can physically play (MIDI note numbers).
RANGES: dict[Instrument, tuple[int, int]] = {
    Instrument.DRUMS: (35, 81),  # GM percussion map
    Instrument.BASS: (28, 67),  # E1-G4
    Instrument.KEYS: (21, 108),
    Instrument.GUITAR: (40, 88),
    Instrument.FLUTE: (60, 96),
    Instrument.VIOLIN: (55, 100),
}


#: Velocity for a note that names neither a velocity nor a kit piece.
DEFAULT_VELOCITY = 90


class Note(BaseModel):
    #: Optional only when `piece` names a drum: the kit supplies the pitch.
    pitch: int = Field(default=-1, ge=-1, le=127)
    start: float = Field(ge=0.0, lt=1.0, description="Position in bar, 0.0-1.0")
    dur: float = Field(gt=0.0, le=4.0, description="Duration in bars")
    #: None on a drum note means "whatever that kit piece is normally struck at".
    vel: int | None = Field(default=None, ge=1, le=127)

    #: How this note is played — "pizz", "palm_mute", "staccato". None is the
    #: instrument's normal voice. Unknown values fall back rather than fail.
    articulation: str | None = Field(default=None, max_length=24)
    #: Drums only: the kit piece struck, e.g. "kick", "ghost_snare". When set,
    #: it supplies the pitch, so an agent never writes a GM number.
    piece: str | None = Field(default=None, max_length=24)
    #: Play legato into the next note rather than re-articulating.
    slur: bool = False
    #: Integer grid position and length a player wrote; the player agent turns
    #: them into `start`/`dur` once it knows how many steps the bar has.
    step: int | None = Field(default=None, ge=0)
    len: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _needs_a_pitch_or_a_piece(self) -> "Note":
        if self.pitch < 0 and not self.piece:
            raise ValueError("a note needs either a pitch or a named kit piece")
        return self

    @property
    def velocity(self) -> int:
        """The velocity to actually play, once defaults are applied."""
        return self.vel if self.vel else DEFAULT_VELOCITY


def salvage_notes(values: Any) -> list[dict[str, Any]]:
    """Keep the notes a model got right, drop the ones it did not.

    A single note written at start 1.0 (the downbeat of the *next* bar) should
    cost that note, not the whole bar. Values that are merely out of range are
    clamped where the intent is unambiguous.
    """
    if not isinstance(values, list):
        return []

    salvaged: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        note = dict(value)
        try:
            start = float(note.get("start", 0.0))
            dur = float(note.get("dur", 0.25))
            # A drum note may name a kit piece instead of a pitch.
            has_piece = bool(note.get("piece"))
            pitch = int(note["pitch"]) if note.get("pitch") is not None else None
            if pitch is None and not has_piece:
                continue
        except (TypeError, ValueError):
            continue

        # A note landing exactly on the next downbeat belongs to the next bar.
        if not 0.0 <= start < 1.0:
            continue
        if pitch is not None and not 0 <= pitch <= 127:
            continue
        if note.get("step") is not None:
            try:
                note["step"] = int(note["step"])
                note["len"] = max(1, int(note.get("len") or 1))
            except (TypeError, ValueError):
                continue
            if note["step"] < 0:
                continue

        note["start"] = start
        note["dur"] = min(4.0, max(0.01, dur))
        if pitch is not None:
            note["pitch"] = pitch
        else:
            note.pop("pitch", None)
        # Leave velocity unset when the model omitted it: a named kit piece
        # supplies its own, and melodic notes fall back to DEFAULT_VELOCITY.
        if note.get("vel") is not None:
            note["vel"] = min(127, max(1, int(note["vel"])))
        else:
            note.pop("vel", None)
        salvaged.append(note)

    return salvaged


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

    @field_validator("notes", mode="before")
    @classmethod
    def _salvage(cls, value: Any) -> Any:
        return salvage_notes(value) if isinstance(value, list) and value and isinstance(
            value[0], dict
        ) else value

    @field_validator("notes")
    @classmethod
    def _notes_in_range(cls, notes: list[Note], info) -> list[Note]:
        """Drop what this instrument cannot physically play.

        A drum note naming a kit piece takes its pitch from that piece, so
        the agent never has to know the General MIDI numbers.
        """
        instrument = info.data.get("instrument")
        if instrument is None:
            return notes

        if instrument is Instrument.DRUMS:
            notes = [n for n in (_resolved_drum(note) for note in notes) if n is not None]

        lo, hi = RANGES[instrument]
        return [n for n in notes if lo <= n.pitch <= hi]


def _resolved_drum(note: Note) -> Note | None:
    """Turn a named kit piece into its pitch and default velocity.

    Returns None when a piece name is given but unrecognised — silently
    turning an unknown surface into a kick drum would be worse than silence.
    """
    from app.core.kit import resolve

    if note.piece is None:
        return note

    piece = resolve(note.piece)
    if piece is None:
        return None
    return note.model_copy(
        update={"pitch": piece.note, "vel": note.vel if note.vel else piece.velocity}
    )


class Bar(BaseModel):
    """All six parts for a single bar, ready to schedule."""

    index: int = Field(ge=0)
    chord: str = "N.C."
    parts: dict[Instrument, BarPart] = Field(default_factory=dict)


def _steps(value: Any) -> list[int]:
    """Keep the step numbers out of whatever list the leader wrote; drop the rest."""
    if not isinstance(value, list):
        return []
    return sorted({int(v) for v in value if isinstance(v, (int, float)) and 0 <= v < 64})


class MotifNote(BaseModel):
    step: int = Field(ge=0, lt=128)
    len: int = Field(default=2, ge=1, le=64)
    degree: int = Field(ge=1, le=7)
    octave_offset: int = Field(default=0, ge=-2, le=2)


class Role(BaseModel, populate_by_name=True):
    #: "register" in the leader's JSON; renamed because BaseModel owns that name.
    band: Literal["low", "mid", "high"] = Field(default="mid", alias="register")
    doubles: Instrument | None = None
    enters_bar: int = Field(default=0, ge=0)

    @field_validator("doubles", mode="before")
    @classmethod
    def _known_doubles(cls, value: Any) -> Any:
        return coerce_optional_instrument(value)


class CallResponse(BaseModel):
    bar: int = Field(ge=0)
    lead: Instrument


class ArrangementBrief(BaseModel):
    """The section's shared score: what everyone agrees on before playing.

    Every field is optional and garbage is dropped item by item, so a bad
    brief degrades to players working from the cue alone.
    """

    groove: dict[str, list[int]] = Field(default_factory=dict)
    bass_rhythm: list[int] = Field(default_factory=list)
    comp_rhythm: list[int] = Field(default_factory=list)
    motif: list[MotifNote] = Field(default_factory=list, max_length=32)
    motif_development: str = Field(default="", max_length=200)
    roles: dict[Instrument, Role] = Field(default_factory=dict)
    energy_curve: list[int] = Field(default_factory=list, max_length=16)
    call_response: list[CallResponse] = Field(default_factory=list, max_length=16)

    @field_validator("groove", mode="before")
    @classmethod
    def _clean_groove(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {}
        return {
            piece: _steps(steps)
            for piece, steps in value.items()
            if piece in ("kick", "snare", "hat")
        }

    @field_validator("bass_rhythm", "comp_rhythm", mode="before")
    @classmethod
    def _clean_steps(cls, value: Any) -> Any:
        return _steps(value)

    @field_validator("motif", "call_response", mode="before")
    @classmethod
    def _drop_bad_items(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, list):
            return []
        item = MotifNote if info.field_name == "motif" else CallResponse
        kept = []
        for raw in value:
            try:
                kept.append(item.model_validate(raw))
            except ValidationError:
                continue
        return kept

    @field_validator("roles", mode="before")
    @classmethod
    def _drop_bad_roles(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {}
        kept: dict[Instrument, Role] = {}
        for name, raw in value.items():
            instrument = coerce_optional_instrument(name)
            if instrument is None:
                continue
            try:
                kept[instrument] = Role.model_validate(raw)
            except ValidationError:
                continue
        return kept

    @field_validator("energy_curve", mode="before")
    @classmethod
    def _clamp_energy(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return []
        return [max(1, min(10, int(v))) for v in value if isinstance(v, (int, float))][:16]

    @field_validator("motif_development", mode="before")
    @classmethod
    def _short_text(cls, value: Any) -> Any:
        return str(value)[:200] if value is not None else ""


class SectionCue(BaseModel):
    """Bandleader's instruction to the players for the next window."""

    section: str = Field(default="verse", max_length=32)
    chords: list[str] = Field(min_length=1, max_length=16)
    energy: int = Field(default=5, ge=1, le=10)
    density: int = Field(default=5, ge=1, le=10)
    soloist: Instrument | None = None
    tacet: list[Instrument] = Field(default_factory=list, description="Sit this window out")
    direction: str = Field(default="", max_length=280)
    brief: ArrangementBrief | None = None

    @field_validator("brief", mode="before")
    @classmethod
    def _lenient_brief(cls, value: Any) -> Any:
        """A brief that is not even an object is no brief at all."""
        return value if isinstance(value, (dict, ArrangementBrief)) else None

    @field_validator("soloist", mode="before")
    @classmethod
    def _known_soloist(cls, value: Any) -> Any:
        return coerce_optional_instrument(value)

    @field_validator("tacet", mode="before")
    @classmethod
    def _known_tacet(cls, value: Any) -> Any:
        return coerce_instruments(value)


class Feel(BaseModel, frozen=True):
    """What every player knows before counting in: key, tempo and meter."""

    key: str | None = None
    tempo: int | None = None
    time_signature: str = "4/4"


class Song(BaseModel):
    title: str = Field(max_length=120)
    key: str = Field(max_length=16)
    tempo: int = Field(ge=40, le=240)
    time_signature: str = Field(default="4/4", max_length=8)
    #: Which drum kit the piece is played on: standard, room, jazz, brush.
    kit: str = Field(default="standard", max_length=16)
    patches: dict[Instrument, Patch] = Field(default_factory=dict)
    bars: list[Bar] = Field(default_factory=list)
