"""Chord symbols to real pitch sets.

The players used to guess which notes fit the harmony. This module works it
out instead, so each prompt carries actual pitch names rather than a chord
symbol the model has to interpret on its own.

Everything here is pitch classes (0-11, C=0) except `register_for`, which
returns MIDI note numbers.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.core.schema import RANGES, Instrument

NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")

_ROOTS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


class Quality(StrEnum):
    MAJOR = "major"
    MINOR = "minor"
    DOMINANT = "dominant"
    MAJOR7 = "major7"
    MINOR7 = "minor7"
    MINOR_MAJ7 = "minor-major7"
    HALF_DIM = "half-diminished"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    SUS2 = "sus2"
    SUS4 = "sus4"
    MAJOR6 = "major6"
    MINOR6 = "minor6"
    POWER = "power"


#: Intervals above the root, in semitones.
_INTERVALS: dict[Quality, tuple[int, ...]] = {
    Quality.MAJOR: (0, 4, 7),
    Quality.MINOR: (0, 3, 7),
    Quality.DOMINANT: (0, 4, 7, 10),
    Quality.MAJOR7: (0, 4, 7, 11),
    Quality.MINOR7: (0, 3, 7, 10),
    Quality.MINOR_MAJ7: (0, 3, 7, 11),
    Quality.HALF_DIM: (0, 3, 6, 10),
    Quality.DIMINISHED: (0, 3, 6, 9),
    Quality.AUGMENTED: (0, 4, 8),
    Quality.SUS2: (0, 2, 7),
    Quality.SUS4: (0, 5, 7),
    Quality.MAJOR6: (0, 4, 7, 9),
    Quality.MINOR6: (0, 3, 7, 9),
    Quality.POWER: (0, 7),  # root and fifth, no third — the chord has no mode
}

#: The mode a player should draw on over each quality, as intervals.
_MODES: dict[Quality, tuple[int, ...]] = {
    Quality.MAJOR: (0, 2, 4, 5, 7, 9, 11),          # ionian
    Quality.MAJOR7: (0, 2, 4, 5, 7, 9, 11),         # ionian
    Quality.MAJOR6: (0, 2, 4, 5, 7, 9, 11),
    Quality.MINOR: (0, 2, 3, 5, 7, 9, 10),          # dorian — the raised 6th sings
    Quality.MINOR7: (0, 2, 3, 5, 7, 9, 10),         # dorian
    Quality.MINOR6: (0, 2, 3, 5, 7, 9, 10),
    Quality.MINOR_MAJ7: (0, 2, 3, 5, 7, 8, 11),     # harmonic minor
    Quality.DOMINANT: (0, 2, 4, 5, 7, 9, 10),       # mixolydian
    Quality.HALF_DIM: (0, 1, 3, 5, 6, 8, 10),       # locrian
    Quality.DIMINISHED: (0, 2, 3, 5, 6, 8, 9, 11),  # whole-half diminished
    Quality.AUGMENTED: (0, 2, 4, 6, 8, 10),         # whole tone
    Quality.SUS2: (0, 2, 4, 5, 7, 9, 10),
    Quality.SUS4: (0, 2, 4, 5, 7, 9, 10),
    # A power chord states no third, so both minor and major thirds are on the
    # table. Aeolian is the safer default for the music that uses them.
    Quality.POWER: (0, 2, 3, 5, 7, 8, 10),
}

#: Scale degrees that clash when sustained over each quality, as intervals.
_AVOID: dict[Quality, tuple[int, ...]] = {
    Quality.MAJOR: (5,),        # the 4th rubs against the 3rd
    Quality.MAJOR7: (5,),
    Quality.MAJOR6: (5,),
    Quality.MINOR: (8,),        # the b6 over a dorian minor
    Quality.MINOR7: (8,),
    Quality.MINOR6: (8,),
    Quality.DOMINANT: (),       # everything is fair game over a dominant
    Quality.HALF_DIM: (),
    Quality.DIMINISHED: (),
    Quality.AUGMENTED: (),
    Quality.SUS2: (4,),         # the 3rd defeats the suspension
    Quality.SUS4: (4,),
    Quality.MINOR_MAJ7: (),
    Quality.POWER: (),          # deliberately ambiguous; nothing is wrong
}

#: Longest first, so "maj7" is not read as "m".
_QUALITY_TOKENS: tuple[tuple[str, Quality], ...] = (
    ("5", Quality.POWER),       # power chord: root and fifth only
    ("add9", Quality.MAJOR),
    ("madd9", Quality.MINOR),
    ("maj7", Quality.MAJOR7),
    ("maj9", Quality.MAJOR7),
    ("M7", Quality.MAJOR7),
    ("m7b5", Quality.HALF_DIM),
    ("min7", Quality.MINOR7),
    ("mmaj7", Quality.MINOR_MAJ7),
    ("mMaj7", Quality.MINOR_MAJ7),
    ("dim7", Quality.DIMINISHED),
    ("dim", Quality.DIMINISHED),
    ("aug", Quality.AUGMENTED),
    ("sus4", Quality.SUS4),
    ("sus2", Quality.SUS2),
    ("sus", Quality.SUS4),
    ("m6", Quality.MINOR6),
    ("m7", Quality.MINOR7),
    ("m9", Quality.MINOR7),
    ("m11", Quality.MINOR7),
    ("m13", Quality.MINOR7),
    ("min", Quality.MINOR),
    ("6", Quality.MAJOR6),
    ("7", Quality.DOMINANT),
    ("9", Quality.DOMINANT),
    ("11", Quality.DOMINANT),
    ("13", Quality.DOMINANT),
    ("m", Quality.MINOR),
    ("-", Quality.MINOR),       # jazz shorthand: C- is C minor
    ("\u00f8", Quality.HALF_DIM),   # C{empty} is half-diminished
    ("", Quality.MAJOR),
)

_SYMBOL = re.compile(r"^([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?$")


@dataclass(frozen=True)
class Chord:
    symbol: str
    root: int
    quality: Quality
    bass: int
    extensions: list[int] = field(default_factory=list)


def parse_chord(symbol: str | None) -> Chord | None:
    """Read a chord symbol. Returns None for "N.C." and anything unparseable.

    Callers treat None as "no fixed harmony" rather than an error — a bar
    marked N.C. is a legitimate musical instruction.
    """
    if not symbol:
        return None
    match = _SYMBOL.match(symbol.strip())
    if match is None:
        return None

    root_name, body, bass_name = match.groups()
    root = _ROOTS[root_name]

    # Extensions are read before the quality token so "Am9" keeps its 9.
    # A power chord is exactly root-and-fifth, so it takes none.
    if body.startswith("5"):
        extensions: list[int] = []
    else:
        extensions = [int(n) for n in re.findall(r"(?:^|[^b#\d])(9|11|13)", body)]
        extensions += [int(n) for n in re.findall(r"[b#](9|11|13)", body)]

    quality = next(
        (q for token, q in _QUALITY_TOKENS if token and body.startswith(token)),
        None,
    )
    if quality is None:
        quality = Quality.MAJOR if body == "" or body[0] in "9111 3" else None
    if quality is None:
        return None

    bass = _ROOTS[bass_name] if bass_name else root
    return Chord(
        symbol=symbol.strip(),
        root=root,
        quality=quality,
        bass=bass,
        extensions=sorted(set(extensions)),
    )


def chord_tones(chord: Chord | None) -> set[int]:
    """The notes that spell the chord, including any written extension."""
    if chord is None:
        return set()
    tones = {(chord.root + i) % 12 for i in _INTERVALS[chord.quality]}
    mode = _MODES[chord.quality]
    for extension in chord.extensions:
        degree = (extension - 1) % 7
        tones.add((chord.root + mode[degree]) % 12)
    tones.add(chord.bass % 12)
    return tones


def scale_for(chord: Chord | None) -> set[int]:
    """The mode a player can move through over this chord."""
    if chord is None:
        return set()
    return {(chord.root + i) % 12 for i in _MODES[chord.quality]} | chord_tones(chord)


def avoid_tones(chord: Chord | None) -> set[int]:
    """Notes that clash if held. Fine in passing, wrong when sustained."""
    if chord is None:
        return set()
    return {(chord.root + i) % 12 for i in _AVOID[chord.quality]} - chord_tones(chord)


def tension_tones(chord: Chord | None) -> set[int]:
    """Scale notes that are not chord tones: the colour a soloist reaches for."""
    if chord is None:
        return set()
    return scale_for(chord) - chord_tones(chord) - avoid_tones(chord)


def pitch_names(
    pitch_classes: set[int],
    root: int | None = None,
    above: set[int] | None = None,
) -> str:
    """"C E G" for a prompt.

    Ordered from C by default. Pass a root to read the chord from its root
    upwards, and `above` to name pitch classes that belong in the upper
    structure (9ths, 11ths, 13ths) so they stack after the seventh.
    """
    if not pitch_classes:
        return "—"
    if root is None:
        return " ".join(NAMES[p] for p in sorted(pitch_classes))

    upper = above or set()

    def degree(pitch: int) -> int:
        interval = (pitch - root) % 12
        return interval + 12 if pitch in upper else interval

    return " ".join(NAMES[p] for p in sorted(pitch_classes, key=degree))


def extension_tones(chord: Chord | None) -> set[int]:
    """The pitch classes contributed by written extensions (9, 11, 13)."""
    if chord is None or not chord.extensions:
        return set()
    mode = _MODES[chord.quality]
    return {(chord.root + mode[(e - 1) % 7]) % 12 for e in chord.extensions}


#: Which slice of its range each player should occupy so five instruments do
#: not all crowd the middle. Fractions of the instrument's full range.
_REGISTERS: dict[Instrument, tuple[float, float]] = {
    Instrument.KEYS: (0.15, 0.70),     # wide, holds the harmony
    Instrument.GUITAR: (0.10, 0.60),   # below the melody
    Instrument.VIOLIN: (0.20, 0.80),
    Instrument.FLUTE: (0.25, 0.85),    # the top voice
    Instrument.DRUMS: (0.0, 1.0),
}


def register_for(instrument: Instrument, *, soloing: bool = False) -> tuple[int, int]:
    """The MIDI window this player should write in.

    A soloist gets more room; everyone else stays in their lane so the
    arrangement has vertical space.
    """
    lo, hi = RANGES[instrument]
    if instrument is Instrument.DRUMS:
        return lo, hi

    low_frac, high_frac = _REGISTERS[instrument]
    if soloing:
        low_frac = max(0.0, low_frac - 0.12)
        high_frac = min(1.0, high_frac + 0.12)

    span = hi - lo
    return lo + round(span * low_frac), lo + round(span * high_frac)


def describe_harmony(symbol: str, instrument: Instrument, *, soloing: bool = False) -> str:
    """The harmony briefing a player receives for one bar.

    Drums get nothing — they are not playing pitches.
    """
    if instrument is Instrument.DRUMS:
        return ""

    low, high = register_for(instrument, soloing=soloing)
    register = f"Your register this bar: MIDI {low}-{high}."

    chord = parse_chord(symbol)
    if chord is None:
        return f"{symbol}: no fixed harmony — play freely. {register}"

    lines = [
        f"Chord {chord.symbol}. "
        f"Chord tones: {pitch_names(chord_tones(chord), chord.root, extension_tones(chord))}.",
        f"Scale: {pitch_names(scale_for(chord), chord.root)}.",
    ]
    tensions = tension_tones(chord)
    if tensions:
        lines.append(f"Colour notes: {pitch_names(tensions, chord.root)}.")
    avoid = avoid_tones(chord)
    if avoid:
        lines.append(f"Avoid landing on: {pitch_names(avoid)}.")
    lines.append(register)
    return " ".join(lines)
