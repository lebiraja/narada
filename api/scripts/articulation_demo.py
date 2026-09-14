"""A short piece that exercises every new instrument capability.

Written by hand into the schema so the articulations, kit pieces and
registers are all provably exercised, then exported through the real path.

    docker compose exec -T -e PYTHONPATH=/app api python scripts/articulation_demo.py
"""

import sys

from app.core.schema import Bar, BarPart, Instrument, Note, Song
from app.core.theory import chord_tones, parse_chord, register_for

TEMPO = 88
PROGRESSION = ["Am9", "Am9", "Dm7", "Dm7", "G7", "G7", "Cmaj7", "Cmaj7",
               "Fmaj7", "Fmaj7", "Bm7b5", "E7", "Am9", "Dm7", "E7", "Am9"]


def in_register(instrument: Instrument, pitch_class: int, *, high: bool = False) -> int:
    """Put a pitch class into this instrument's register."""
    lo, hi = register_for(instrument)
    target = hi - 4 if high else lo + (hi - lo) // 3
    candidates = [p for p in range(lo, hi + 1) if p % 12 == pitch_class]
    return min(candidates, key=lambda p: abs(p - target)) if candidates else target


def violin(bar: int, chord: str) -> list[Note]:
    """Bowed melody, answered by pizzicato in the middle section."""
    tones = sorted(chord_tones(parse_chord(chord)))
    root = parse_chord(chord).root

    if 4 <= bar <= 7:  # pizzicato answer
        return [
            Note(pitch=in_register(Instrument.VIOLIN, tones[i % len(tones)]),
                 start=i * 0.25, dur=0.2, vel=76, articulation="pizz")
            for i in range(4)
        ]
    if bar in (10, 11):  # tension before the turnaround
        return [Note(pitch=in_register(Instrument.VIOLIN, root, high=True),
                     start=0.0, dur=0.95, vel=70, articulation="tremolo")]
    if bar >= 14:
        return [Note(pitch=in_register(Instrument.VIOLIN, root, high=True),
                     start=0.0, dur=0.9, vel=64)]

    return [
        Note(pitch=in_register(Instrument.VIOLIN, root, high=True),
             start=0.0, dur=0.45, vel=80, slur=True),
        Note(pitch=in_register(Instrument.VIOLIN, tones[2 % len(tones)], high=True),
             start=0.5, dur=0.45, vel=74),
    ]


def flute(bar: int, chord: str) -> list[Note]:
    """Enters as a recorder, becomes a flute when the band opens up."""
    if bar < 2:
        return []
    tones = sorted(chord_tones(parse_chord(chord)))
    voice = "recorder" if bar < 8 else None
    return [
        Note(pitch=in_register(Instrument.FLUTE, tones[(i + 1) % len(tones)], high=True),
             start=0.25 + i * 0.25, dur=0.22, vel=62 + i * 4, articulation=voice)
        for i in range(2)
    ]


def keys(bar: int, chord: str) -> list[Note]:
    """Rhodes throughout, holding the low end since there is no bass."""
    parsed = parse_chord(chord)
    tones = sorted(chord_tones(parsed))
    lo, _ = register_for(Instrument.KEYS)

    bass = min((p for p in range(lo, lo + 24) if p % 12 == parsed.bass % 12), default=lo)
    voicing = [in_register(Instrument.KEYS, t) for t in tones[1:4]]

    notes = [Note(pitch=bass, start=0.0, dur=0.9, vel=54, articulation="rhodes")]
    notes += [
        Note(pitch=p, start=0.0, dur=0.85, vel=44 + i, articulation="rhodes")
        for i, p in enumerate(voicing)
    ]
    if 6 <= bar <= 12:
        notes.append(Note(pitch=voicing[-1], start=0.5, dur=0.4, vel=40,
                          articulation="rhodes"))
    return notes


def guitar(bar: int, chord: str) -> list[Note]:
    """Palm-muted groove, opening to harmonics at the end."""
    if bar < 1:
        return []
    tones = sorted(chord_tones(parse_chord(chord)))

    if bar >= 14:
        return [Note(pitch=in_register(Instrument.GUITAR, tones[0]),
                     start=0.0, dur=0.5, vel=58, articulation="harmonics")]
    if bar in (8, 9):  # nylon for the softer section
        return [
            Note(pitch=in_register(Instrument.GUITAR, tones[i % len(tones)]),
                 start=i * 0.25, dur=0.22, vel=56, articulation="nylon")
            for i in range(4)
        ]
    return [
        Note(pitch=in_register(Instrument.GUITAR, tones[i % len(tones)]),
             start=i / 8, dur=0.1, vel=52 + (8 if i % 2 == 0 else 0),
             articulation="palm_mute")
        for i in range(8)
    ]


def drums(bar: int, chord: str) -> list[Note]:
    """Named kit pieces, ghost notes, and a flam into the last section."""
    if bar < 1:
        return []

    notes = [Note(piece="kick", start=0.0, dur=0.1)]
    notes += [Note(piece="hat_closed", start=i * 0.25, dur=0.06) for i in range(1, 4)]

    if bar >= 2:
        notes.append(Note(piece="snare", start=0.5, dur=0.1))
        notes.append(Note(piece="ghost_snare", start=0.375, dur=0.06))
    if bar >= 6:
        notes.append(Note(piece="kick", start=0.625, dur=0.1))
        notes.append(Note(piece="ghost_snare", start=0.875, dur=0.06))
    if bar >= 10:
        notes.append(Note(piece="ride", start=0.75, dur=0.1, articulation="accent"))
    if bar == 11:  # a flam: two hits a hair apart
        notes.append(Note(piece="snare", start=0.73, dur=0.08, vel=70))
        notes.append(Note(piece="snare", start=0.75, dur=0.1, vel=100))
    if bar == 12:
        notes.append(Note(piece="crash", start=0.0, dur=0.3))
    if bar >= 14:
        notes = [Note(piece="ride", start=0.0, dur=0.4, vel=54)]
    return notes


WRITERS = {
    Instrument.VIOLIN: violin,
    Instrument.FLUTE: flute,
    Instrument.KEYS: keys,
    Instrument.GUITAR: guitar,
    Instrument.DRUMS: drums,
}


def build() -> Song:
    song = Song(title="Veena", key="A dorian", tempo=TEMPO,
                time_signature="4/4", kit="brush")
    for index, chord in enumerate(PROGRESSION):
        song.bars.append(Bar(index=index, chord=chord, parts={
            instrument: BarPart(instrument=instrument, bar=index,
                                notes=write(index, chord), patch=None)
            for instrument, write in WRITERS.items()
        }))
    return song


if __name__ == "__main__":
    song = build()
    used = {n.articulation for b in song.bars for p in b.parts.values()
            for n in p.notes if n.articulation}
    pieces = {n.piece for b in song.bars for p in b.parts.values()
              for n in p.notes if n.piece}
    total = sum(len(p.notes) for b in song.bars for p in b.parts.values())
    print(f"{song.title} — {song.key}, {song.time_signature}, {song.tempo}bpm, "
          f"{song.kit} kit", file=sys.stderr)
    print(f"{len(song.bars)} bars, {total} notes", file=sys.stderr)
    print(f"articulations: {sorted(used)}", file=sys.stderr)
    print(f"kit pieces: {sorted(pieces)}", file=sys.stderr)
    print(song.model_dump_json())
