"""'Monsoon Letters' — a piece written directly into the band's own schema.

Thirty seconds in 6/8 at 76 bpm, A dorian. The violin states a theme, the
flute answers it a bar later, the keys hold quartal voicings underneath, the
guitar arpeggiates, and the drums stay brushed until a late lift.

Written as data, exactly like the agents write it, so it exports to stems and
plays in the browser through the same path.

    docker compose exec -T -e PYTHONPATH=/app api python scripts/compose_monsoon.py
"""

import json
import sys

from app.core.schema import Bar, BarPart, Instrument, Note, Patch, Song

TEMPO = 84
BARS = 16  # 16 bars of 6/8 at 76bpm ≈ 30s

# A dorian: A B C D E F# G. The raised 6th is what keeps it from being sad.
A, B, C, D, E, FS, G = 69, 71, 72, 74, 76, 78, 79

#: Harmonic plan — each bar's chord, as scale-degree stacks.
PROGRESSION = [
    "Am9", "Am9", "Dm7", "Dm7",
    "G6", "G6", "Cmaj7", "Cmaj7",
    "Am9", "Am9", "Fmaj7", "Fmaj7",
    "Dm7", "G6", "Am9", "Am9",
]

# Quartal keyboard voicings (stacked fourths — open, modal, not jazz-club).
VOICINGS: dict[str, list[int]] = {
    "Am9": [57, 62, 67, 71],
    "Dm7": [50, 57, 62, 65],
    "G6": [55, 62, 64, 69],
    "Cmaj7": [48, 55, 59, 64],
    "Fmaj7": [53, 60, 64, 69],
}

# Guitar arpeggio shapes, low to high.
SHAPES: dict[str, list[int]] = {
    "Am9": [45, 52, 57, 64],
    "Dm7": [50, 57, 62, 65],
    "G6": [43, 50, 55, 64],
    "Cmaj7": [48, 55, 60, 64],
    "Fmaj7": [41, 48, 53, 60],
}


def swung(position: float) -> float:
    """In 6/8 the pulse is two dotted beats; nudge the offbeats to breathe."""
    return position


def violin_line(bar: int, chord: str) -> list[Note]:
    """The theme: a rising sixth that falls back, stated then varied."""
    phrases: dict[int, list[tuple[int, float, float, int]]] = {
        0: [(A, 0.0, 0.33, 70), (C + 12 - 12, 0.33, 0.17, 66), (E, 0.5, 0.5, 74)],
        1: [(D + 12 - 12, 0.0, 0.25, 72), (C, 0.25, 0.08, 64), (B, 0.33, 0.17, 68), (A, 0.5, 0.5, 70)],
        2: [(D, 0.0, 0.33, 74), (E, 0.33, 0.17, 70), (FS, 0.5, 0.5, 78)],
        3: [(E, 0.0, 0.25, 72), (D, 0.25, 0.25, 68), (C, 0.5, 0.5, 70)],
        4: [(B, 0.0, 0.33, 76), (D, 0.33, 0.17, 72), (G + 12, 0.5, 0.5, 82)],
        5: [(FS + 12 - 12, 0.0, 0.25, 74), (E, 0.25, 0.25, 70), (D, 0.5, 0.5, 72)],
        6: [(E, 0.0, 0.5, 76), (G, 0.5, 0.5, 74)],
        7: [(A + 12, 0.0, 0.66, 84), (G + 12, 0.66, 0.34, 76)],
        8: [(A, 0.0, 0.33, 72), (C, 0.33, 0.17, 68), (E, 0.5, 0.5, 76)],
        9: [(FS, 0.0, 0.25, 74), (E, 0.25, 0.25, 70), (D, 0.5, 0.5, 72)],
        10: [(C + 12, 0.0, 0.5, 84), (A + 12, 0.5, 0.5, 80)],
        11: [(G + 12, 0.0, 0.33, 78), (FS + 12, 0.33, 0.17, 74), (E + 12, 0.5, 0.5, 82)],
        12: [(D + 12, 0.0, 0.33, 80), (C + 12, 0.33, 0.17, 76), (B, 0.5, 0.5, 78)],
        13: [(B, 0.0, 0.25, 76), (D + 12, 0.25, 0.25, 80), (E + 12, 0.5, 0.5, 86)],
        14: [(A + 12, 0.0, 0.66, 82), (E, 0.66, 0.34, 70)],
        15: [(A, 0.0, 1.0, 66)],
    }
    return [
        Note(pitch=p, start=swung(s), dur=d, vel=v) for p, s, d, v in phrases.get(bar, [])
    ]


def flute_line(bar: int, chord: str) -> list[Note]:
    """The answer: echoes the violin a bar late, higher, with breath between."""
    phrases: dict[int, list[tuple[int, float, float, int]]] = {
        1: [(A + 12, 0.5, 0.5, 58)],
        2: [(E + 12, 0.0, 0.33, 62), (D + 12, 0.33, 0.17, 56)],
        3: [(FS + 12, 0.0, 0.25, 64), (E + 12, 0.25, 0.25, 58), (D + 12, 0.5, 0.33, 60)],
        5: [(B + 12, 0.0, 0.33, 66), (A + 12, 0.33, 0.17, 60), (G + 12, 0.5, 0.5, 64)],
        6: [(E + 12, 0.0, 0.5, 68)],
        7: [(C + 24 - 12, 0.0, 0.33, 72), (B + 12, 0.33, 0.17, 64), (A + 12, 0.5, 0.5, 68)],
        9: [(D + 12, 0.5, 0.5, 62)],
        10: [(A + 12, 0.0, 0.33, 70), (C + 24 - 12, 0.33, 0.17, 66), (E + 24 - 12, 0.5, 0.5, 76)],
        11: [(D + 24 - 12, 0.0, 0.25, 74), (C + 24 - 12, 0.25, 0.25, 68), (A + 12, 0.5, 0.5, 70)],
        12: [(FS + 12, 0.0, 0.5, 68), (E + 12, 0.5, 0.5, 64)],
        13: [(G + 12, 0.0, 0.33, 72), (A + 12, 0.33, 0.17, 66), (B + 12, 0.5, 0.5, 74)],
        14: [(E + 24 - 12, 0.0, 0.66, 78), (A + 12, 0.66, 0.34, 64)],
        15: [(A + 12, 0.0, 1.0, 56)],
    }
    return [Note(pitch=p, start=s, dur=d, vel=v) for p, s, d, v in phrases.get(bar, [])]


def keys_line(bar: int, chord: str) -> list[Note]:
    """Quartal pads, entering softly and thinning out at the end."""
    voicing = VOICINGS[chord]
    if bar == 0:
        voicing = voicing[:2]  # start almost bare
    if bar >= 14:
        voicing = voicing[:3]

    vel = 34 + min(bar, 10) * 2
    notes = [Note(pitch=p, start=0.0, dur=0.92, vel=vel + i) for i, p in enumerate(voicing)]

    # A gentle re-articulation on the second dotted beat keeps the pad alive.
    if 4 <= bar <= 13:
        notes.append(Note(pitch=voicing[-1] + 5, start=0.5, dur=0.45, vel=vel - 6))
    return notes


def guitar_line(bar: int, chord: str) -> list[Note]:
    """Arpeggios in 6/8: low, middle, high, middle — a rolling figure."""
    if bar < 2:
        return []
    shape = SHAPES[chord]
    order = [0, 2, 3, 1, 2, 3]
    vel_base = 44 + min(bar, 12)
    return [
        Note(
            pitch=shape[order[i]],
            start=i / 6,
            dur=0.2,
            vel=vel_base + (6 if i % 3 == 0 else 0) - (4 if i % 2 else 0),
        )
        for i in range(6)
    ]


def drums_line(bar: int, chord: str) -> list[Note]:
    """Brushes. Ride pulse throughout, kick on the dotted beats, a late lift."""
    KICK, SNARE, RIDE, HAT, TOM = 36, 38, 51, 42, 45

    if bar < 3:
        return []
    if bar < 6:
        return [Note(pitch=RIDE, start=i / 6, dur=0.12, vel=30 + (10 if i % 3 == 0 else 0))
                for i in range(6)]

    notes = [
        Note(pitch=RIDE, start=i / 6, dur=0.12, vel=34 + (12 if i % 3 == 0 else 0))
        for i in range(6)
    ]
    notes.append(Note(pitch=KICK, start=0.0, dur=0.15, vel=62))
    notes.append(Note(pitch=SNARE, start=0.5, dur=0.15, vel=44))

    if bar >= 10:  # the lift
        notes.append(Note(pitch=KICK, start=0.33, dur=0.12, vel=48))
        notes.append(Note(pitch=HAT, start=0.83, dur=0.1, vel=38))
    if bar == 13:  # a small tom fill into the last phrase
        notes.extend([
            Note(pitch=TOM, start=0.66, dur=0.12, vel=58),
            Note(pitch=TOM - 2, start=0.83, dur=0.12, vel=64),
        ])
    if bar == 15:
        return [Note(pitch=RIDE, start=0.0, dur=0.5, vel=40)]
    return notes


WRITERS = {
    Instrument.VIOLIN: violin_line,
    Instrument.FLUTE: flute_line,
    Instrument.KEYS: keys_line,
    Instrument.GUITAR: guitar_line,
    Instrument.DRUMS: drums_line,
}

# Voices the players chose for themselves, in the schema's patch format.
PATCHES = {
    Instrument.VIOLIN: Patch(oscillator="fmsine", attack=0.12, decay=0.3, sustain=0.85,
                             release=0.9, filter_freq=7000, filter_q=1.4, reverb=0.45, delay=0.0),
    Instrument.FLUTE: Patch(oscillator="sine", attack=0.09, decay=0.15, sustain=0.9,
                            release=0.5, filter_freq=11000, filter_q=1.0, reverb=0.4, delay=0.1),
    Instrument.KEYS: Patch(oscillator="triangle", attack=0.02, decay=0.5, sustain=0.45,
                           release=1.6, filter_freq=6500, filter_q=1.2, reverb=0.35, delay=0.0),
}


def build() -> Song:
    song = Song(
        title="Monsoon Letters",
        key="A dorian",
        tempo=TEMPO,
        time_signature="6/8",
        patches=PATCHES,
    )
    for index in range(BARS):
        chord = PROGRESSION[index]
        song.bars.append(
            Bar(
                index=index,
                chord=chord,
                parts={
                    instrument: BarPart(
                        instrument=instrument,
                        bar=index,
                        notes=write(index, chord),
                        patch=None,
                    )
                    for instrument, write in WRITERS.items()
                },
            )
        )
    return song


if __name__ == "__main__":
    song = build()
    total = sum(len(p.notes) for bar in song.bars for p in bar.parts.values())
    print(f"{song.title} — {song.key}, {song.time_signature}, {song.tempo}bpm", file=sys.stderr)
    print(f"{len(song.bars)} bars, {total} notes", file=sys.stderr)
    print(song.model_dump_json())
