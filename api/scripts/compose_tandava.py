"""'Tandava' — a heavy piece in 7/8.

Named for Shiva's dance of destruction, which is the right register for a
riff in seven. Drums and guitar drive it; with no bass player in the band the
keys own the low end, doubling the riff two octaves down.

The bar is counted 3+2+2: DA-da-da DA-da DA-da. Everything lands on those
three accents, which is what makes seven feel like a lurch rather than a
mistake.

    docker compose exec -T -e PYTHONPATH=/app api python scripts/compose_tandava.py
"""

import sys

from app.core.schema import Bar, BarPart, Instrument, Note, Song

TEMPO = 132
BARS = 28

# In 7/8 one eighth is 1/7 of the bar.
E8 = 1 / 7

#: The 3+2+2 grouping: accents fall on eighths 0, 3 and 5.
ACCENTS = (0, 3, 5)

# E aeolian: E F# G A B C D. The riff lives on the bottom three strings.
E2, FS2, G2, A2, B2, C3, D3 = 40, 42, 43, 45, 47, 48, 50
E3 = 52

#: The main riff, as (eighth, pitch) — a low E pedal punctured by the b2 and 4.
RIFF = ((0, E2), (1, E2), (2, G2), (3, E2), (4, A2), (5, E2), (6, FS2))
#: The answering figure, used in the second half of each phrase.
RIFF_B = ((0, E2), (1, E2), (2, D3), (3, C3), (4, B2), (5, E2), (6, G2))

PROGRESSION = (
    ["E5"] * 4                      # 0-3    riff alone, building
    + ["E5", "E5", "G5", "A5"]      # 4-7    band in
    + ["E5", "E5", "C5", "D5"]      # 8-11   first turn
    + ["E5", "E5", "G5", "A5"]      # 12-15  heavier
    + ["C5", "C5", "G5", "G5"]      # 16-19  the lift — violin takes it
    + ["A5", "A5", "B5", "B5"]      # 20-23  tension
    + ["E5", "E5", "G5", "A5"]      # 24-27  last statement, then out
)


def section(bar: int) -> str:
    if bar < 4:
        return "intro"
    if bar < 16:
        return "riff"
    if bar < 20:
        return "lift"
    if bar < 24:
        return "tension"
    return "out"


def transpose_riff(figure, semitones: int):
    return tuple((e, p + semitones) for e, p in figure)


#: How far each chord sits from E.
OFFSET = {"E5": 0, "G5": 3, "A5": 5, "C5": 8, "D5": 10, "B5": 7}


def guitar(bar: int, chord: str) -> list[Note]:
    """The riff. Palm-muted until the lift, then let to ring."""
    figure = RIFF_B if bar % 4 == 3 and bar >= 8 else RIFF
    figure = transpose_riff(figure, OFFSET[chord])
    part = section(bar)

    if part == "lift":
        # Let the chords ring out — one sustained power chord per bar.
        root = E2 + OFFSET[chord]
        return [
            Note(pitch=root, start=0.0, dur=0.95, vel=104, articulation="overdrive"),
            Note(pitch=root + 7, start=0.0, dur=0.95, vel=98, articulation="overdrive"),
            Note(pitch=root + 12, start=0.0, dur=0.95, vel=92, articulation="overdrive"),
        ]

    voice = "palm_mute" if part in ("intro", "riff") else "overdrive"
    notes: list[Note] = []
    for eighth, pitch in figure:
        accented = eighth in ACCENTS
        notes.append(
            Note(
                pitch=pitch,
                start=eighth * E8,
                dur=E8 * (0.9 if accented else 0.55),
                vel=(120 if accented else 84) - (14 if part == "intro" else 0),
                articulation=voice,
            )
        )
        # The fifth doubles the accents — that is what makes it a wall.
        if accented and part != "intro":
            notes.append(
                Note(pitch=pitch + 7, start=eighth * E8, dur=E8 * 0.9, vel=100,
                     articulation=voice)
            )
    return notes


def keys(bar: int, chord: str) -> list[Note]:
    """No bass player, so the keys are the bass — riff doubled two octaves down."""
    if bar < 2:
        return []
    figure = transpose_riff(RIFF_B if bar % 4 == 3 and bar >= 8 else RIFF, OFFSET[chord])
    part = section(bar)

    if part == "lift":
        root = E2 + OFFSET[chord] - 12
        return [
            Note(pitch=root, start=0.0, dur=0.95, vel=96),
            Note(pitch=root + 7, start=0.0, dur=0.95, vel=84),
            Note(pitch=root + 19, start=0.0, dur=0.9, vel=70, articulation="bright"),
        ]

    notes = [
        Note(pitch=pitch - 12, start=eighth * E8,
             dur=E8 * (0.85 if eighth in ACCENTS else 0.5),
             vel=104 if eighth in ACCENTS else 78)
        for eighth, pitch in figure
    ]
    # A stabbed chord on the downbeat gives the low end some teeth.
    if part in ("riff", "tension"):
        root = E2 + OFFSET[chord]
        notes += [
            Note(pitch=root + 12, start=0.0, dur=E8 * 0.8, vel=72, articulation="bright"),
            Note(pitch=root + 19, start=0.0, dur=E8 * 0.8, vel=66, articulation="bright"),
        ]
    return notes


def drums(bar: int, chord: str) -> list[Note]:
    """Kick on the three accents, snare on the 3+2 boundary, ride through the lift."""
    part = section(bar)

    if part == "intro":
        if bar < 2:
            return []
        # Sticks counting the seven in, so the meter is audible before the band.
        return [
            Note(piece="sticks", start=e * E8, dur=E8 * 0.4,
                 vel=70 if e in ACCENTS else 40)
            for e in range(7)
        ]

    notes: list[Note] = []

    # The 3+2+2 skeleton: kick marks every accent.
    for eighth in ACCENTS:
        notes.append(Note(piece="kick", start=eighth * E8, dur=E8 * 0.5, vel=118))

    # Snare on eighth 3 — the seam between the 3 and the first 2.
    notes.append(Note(piece="snare", start=3 * E8, dur=E8 * 0.5, vel=118,
                      articulation="accent"))
    if part in ("riff", "tension", "out"):
        notes.append(Note(piece="snare", start=5 * E8, dur=E8 * 0.5, vel=104))

    # Eighths on the hat or ride, accented on the grouping.
    surface = "ride" if part == "lift" else "hat_closed"
    for eighth in range(7):
        notes.append(
            Note(piece=surface, start=eighth * E8, dur=E8 * 0.4,
                 vel=92 if eighth in ACCENTS else 62)
        )

    # Ghost notes in the gaps — what stops it sounding programmed.
    if part in ("riff", "out"):
        notes.append(Note(piece="ghost_snare", start=2 * E8 + E8 * 0.5, dur=E8 * 0.3))
        notes.append(Note(piece="ghost_snare", start=6 * E8, dur=E8 * 0.3))

    if bar % 4 == 0:
        notes.append(Note(piece="crash", start=0.0, dur=E8 * 2, vel=120))
    if part == "lift":
        notes.append(Note(piece="ride_bell", start=0.0, dur=E8 * 0.6, vel=110))

    # A tom fill into each new section.
    if bar in (15, 19, 23):
        notes = [n for n in notes if n.piece not in ("hat_closed", "ride")]
        for i, piece in enumerate(("tom_hi", "tom_hi", "tom_mid", "tom_mid",
                                   "tom_lo", "tom_lo", "tom_floor")):
            notes.append(Note(piece=piece, start=i * E8, dur=E8 * 0.6,
                              vel=96 + i * 4))

    if bar == BARS - 1:
        return [
            Note(piece="crash", start=0.0, dur=0.9, vel=127),
            Note(piece="kick", start=0.0, dur=0.3, vel=127),
        ]
    return notes


def violin(bar: int, chord: str) -> list[Note]:
    """Silent until the lift, then a soaring line over the top."""
    part = section(bar)
    root = E2 + OFFSET[chord] + 24

    if part == "tension":
        # Tremolo on the fifth: dread, not melody.
        return [Note(pitch=root + 7, start=0.0, dur=0.95, vel=96,
                     articulation="tremolo")]
    if part == "lift":
        line = ((0, 0), (3, 3), (5, 7)) if bar % 2 == 0 else ((0, 10), (3, 7), (5, 3))
        return [
            Note(pitch=root + interval, start=eighth * E8,
                 dur=E8 * (2.4 if eighth == 5 else 2.0), vel=108, slur=True)
            for eighth, interval in line
        ]
    if part == "out" and bar >= 26:
        return [Note(pitch=root + 12, start=0.0, dur=0.95, vel=112)]
    return []


def flute(bar: int, chord: str) -> list[Note]:
    """Doubles the violin an octave up at the peak, and nowhere else."""
    if section(bar) != "lift" or bar % 2 != 0:
        return []
    root = E2 + OFFSET[chord] + 36
    return [
        Note(pitch=root, start=0.0, dur=E8 * 2.5, vel=88),
        Note(pitch=root + 3, start=3 * E8, dur=E8 * 3.5, vel=94),
    ]


WRITERS = {
    Instrument.GUITAR: guitar,
    Instrument.KEYS: keys,
    Instrument.DRUMS: drums,
    Instrument.VIOLIN: violin,
    Instrument.FLUTE: flute,
}


def build() -> Song:
    song = Song(title="Tandava", key="E aeolian", tempo=TEMPO,
                time_signature="7/8", kit="standard")
    for index in range(BARS):
        chord = PROGRESSION[index]
        song.bars.append(Bar(index=index, chord=chord, parts={
            instrument: BarPart(instrument=instrument, bar=index,
                                notes=write(index, chord), patch=None)
            for instrument, write in WRITERS.items()
        }))
    return song


if __name__ == "__main__":
    song = build()
    total = sum(len(p.notes) for b in song.bars for p in b.parts.values())
    arts = {n.articulation for b in song.bars for p in b.parts.values()
            for n in p.notes if n.articulation}
    pieces = {n.piece for b in song.bars for p in b.parts.values() for n in p.notes if n.piece}
    print(f"{song.title} — {song.key}, {song.time_signature}, {song.tempo}bpm",
          file=sys.stderr)
    print(f"{len(song.bars)} bars, {total} notes", file=sys.stderr)
    print(f"articulations: {sorted(arts)}", file=sys.stderr)
    print(f"kit: {sorted(pieces)}", file=sys.stderr)
    print(song.model_dump_json())
