"""The drum kit, by name.

Agents wrote raw GM note numbers and got them wrong. A drummer thinks
"ghost snare on the e of two", not "note 38 at velocity 25", so the schema
now accepts piece names and does the mapping here.
"""

from dataclasses import dataclass
from enum import StrEnum


class Kit(StrEnum):
    """Which kit the drummer is behind, as real soundfont presets."""

    STANDARD = "standard"
    ROOM = "room"
    JAZZ = "jazz"
    BRUSH = "brush"
    ORCHESTRA = "orchestra"


#: GM percussion bank is 128; these are the preset numbers within it.
KIT_PRESETS: dict[Kit, int] = {
    Kit.STANDARD: 0,
    Kit.ROOM: 8,
    Kit.JAZZ: 32,
    Kit.BRUSH: 40,
    Kit.ORCHESTRA: 48,
}

KIT_DESCRIPTIONS: dict[Kit, str] = {
    Kit.STANDARD: "standard kit — sticks, general purpose",
    Kit.ROOM: "room kit — bigger ambience, more air around the drums",
    Kit.JAZZ: "jazz kit — lighter, tighter, ride-forward",
    Kit.BRUSH: "brushes — swept snare, quiet, for a ballad",
    Kit.ORCHESTRA: "orchestral percussion — timpani and concert instruments",
}


@dataclass(frozen=True)
class Piece:
    """One striking surface, and how hard it is normally struck."""

    name: str
    note: int
    velocity: int
    description: str


#: Named kit pieces on the General MIDI percussion map.
PIECES: tuple[Piece, ...] = (
    Piece("kick", 36, 100, "bass drum — the floor of the groove"),
    Piece("kick_soft", 35, 70, "acoustic bass drum, softer"),
    Piece("snare", 38, 95, "snare, centre hit — the backbeat"),
    Piece("snare_rim", 37, 70, "rimshot / stick click"),
    Piece("ghost_snare", 38, 28, "ghost note on the snare — felt, not heard"),
    Piece("snare_roll", 40, 60, "electric snare, good for rolls"),
    Piece("hat_closed", 42, 70, "closed hi-hat — the pulse"),
    Piece("hat_pedal", 44, 55, "pedalled hi-hat, foot chick"),
    Piece("hat_open", 46, 80, "open hi-hat — lifts the end of a phrase"),
    Piece("ride", 51, 70, "ride cymbal, on the bow"),
    Piece("ride_bell", 53, 85, "ride bell — bright, marks a section"),
    Piece("crash", 49, 100, "crash — arrivals only"),
    Piece("splash", 55, 75, "splash cymbal, quick accent"),
    Piece("china", 52, 95, "china / trashy crash"),
    Piece("tom_hi", 50, 85, "high tom"),
    Piece("tom_mid", 47, 85, "mid tom"),
    Piece("tom_lo", 43, 85, "low tom / floor tom"),
    Piece("tom_floor", 41, 85, "lowest floor tom"),
    Piece("cowbell", 56, 80, "cowbell"),
    Piece("tambourine", 54, 70, "tambourine"),
    Piece("shaker", 70, 60, "maracas / shaker"),
    Piece("clap", 39, 85, "hand clap"),
    Piece("sticks", 31, 60, "sticks together, count-in"),
)

BY_NAME: dict[str, Piece] = {piece.name: piece for piece in PIECES}

#: Names a model may reasonably use for the same surface.
_ALIASES: dict[str, str] = {
    "bass_drum": "kick",
    "bassdrum": "kick",
    "bd": "kick",
    "bass": "kick",
    "kick_drum": "kick",
    "sn": "snare",
    "snare_drum": "snare",
    "backbeat": "snare",
    "rimshot": "snare_rim",
    "rim": "snare_rim",
    "ghost": "ghost_snare",
    "hihat": "hat_closed",
    "hi_hat": "hat_closed",
    "hat": "hat_closed",
    "closed_hat": "hat_closed",
    "open_hat": "hat_open",
    "hh_open": "hat_open",
    "pedal_hat": "hat_pedal",
    "ride_cymbal": "ride",
    "bell": "ride_bell",
    "crash_cymbal": "crash",
    "high_tom": "tom_hi",
    "mid_tom": "tom_mid",
    "low_tom": "tom_lo",
    "floor_tom": "tom_floor",
    "rack_tom": "tom_hi",
}


def resolve(name: str | None) -> Piece | None:
    """Find a kit piece by name, tolerating spaces, case and common synonyms."""
    if not name:
        return None
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    if key in BY_NAME:
        return BY_NAME[key]
    alias = _ALIASES.get(key)
    return BY_NAME.get(alias) if alias else None


def describe_kit() -> str:
    """The kit map a drummer sees in its prompt."""
    return "\n".join(f'  "{p.name}" — {p.description}' for p in PIECES)


def piece_names() -> list[str]:
    """Every accepted piece name, canonical spellings only."""
    return [p.name for p in PIECES]
