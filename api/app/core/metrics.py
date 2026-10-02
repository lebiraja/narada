"""Ensemble metrics: numbers for "is the band playing together".

Pure functions over a finished Song. Each rate is a fraction in 0.0-1.0, or
None when the song gives it nothing to measure (no chords, no bass line).
"""

from itertools import combinations
from typing import Any

from app.core.meter import parse_time_signature, steps_per_bar
from app.core.schema import Bar, Instrument, Note, Song
from app.core.theory import chord_tones, parse_chord, scale_for

#: How far from a grid step an onset may sit, in steps, and still be on it.
GRID_TOLERANCE = 0.1
#: GM kick drums: acoustic bass drum and bass drum 1.
KICK_PITCHES = frozenset({35, 36})
#: Notes below this are bass-register (G3).
BASS_CEILING = 55
#: Intervals that grind when sounded together: minor 2nd / major 7th, tritone.
CLASH_INTERVALS = frozenset({1, 6, 11})
#: Strong beats as positions in the bar: the downbeat and the half-bar.
STRONG_BEATS = (0.0, 0.5)


def _ratio(hits: int, total: int) -> float | None:
    return hits / total if total else None


def _melodic(bar: Bar) -> dict[Instrument, list[Note]]:
    return {i: p.notes for i, p in bar.parts.items() if i is not Instrument.DRUMS}


def _step(note: Note, steps: int) -> float:
    return note.start * steps


def _on_grid(note: Note, steps: int) -> bool:
    position = _step(note, steps)
    return abs(position - round(position)) <= GRID_TOLERANCE


def on_grid_rate(song: Song) -> float | None:
    """Fraction of all onsets that land on the sixteenth-note grid."""
    steps = steps_per_bar(song.time_signature)
    notes = [n for bar in song.bars for part in bar.parts.values() for n in part.notes]
    return _ratio(sum(_on_grid(n, steps) for n in notes), len(notes))


def lowest_part(song: Song) -> Instrument | None:
    """The non-drum part with the lowest average pitch: the de facto bass."""
    pitches: dict[Instrument, list[int]] = {}
    for bar in song.bars:
        for instrument, notes in _melodic(bar).items():
            pitches.setdefault(instrument, []).extend(n.pitch for n in notes)
    sounding = {i: sum(p) / len(p) for i, p in pitches.items() if p}
    return min(sounding, key=sounding.__getitem__) if sounding else None


def kick_bass_lock(song: Song, instrument: Instrument) -> float | None:
    """Fraction of `instrument`'s bass-register onsets within one step of a kick."""
    steps = steps_per_bar(song.time_signature)
    hits = total = 0
    for bar in song.bars:
        drums = bar.parts.get(Instrument.DRUMS)
        kicks = [n.start for n in drums.notes if n.pitch in KICK_PITCHES] if drums else []
        part = bar.parts.get(instrument)
        onsets = {n.start for n in part.notes if n.pitch < BASS_CEILING} if part else set()
        for onset in onsets:
            total += 1
            hits += any(abs(onset - kick) * steps <= 1 for kick in kicks)
    return _ratio(hits, total)


def chord_tone_on_strong_beat_rate(song: Song) -> float | None:
    """Fraction of non-drum notes struck on a strong beat that are chord tones."""
    steps = steps_per_bar(song.time_signature)
    hits = total = 0
    for bar in song.bars:
        tones = chord_tones(parse_chord(bar.chord))
        if not tones:
            continue
        for notes in _melodic(bar).values():
            for note in notes:
                if any(abs(note.start - beat) * steps <= GRID_TOLERANCE for beat in STRONG_BEATS):
                    total += 1
                    hits += note.pitch % 12 in tones
    return _ratio(hits, total)


def _overlaps(a: Note, b: Note) -> bool:
    return a.start < b.start + b.dur and b.start < a.start + a.dur


def clash_rate(song: Song) -> float | None:
    """Fraction of overlapping note pairs between different parts that clash.

    A m2/M7 or tritone is a clash unless both notes are chord tones — a G7's
    B and F are meant to rub.
    """
    clashes = total = 0
    for bar in song.bars:
        tones = chord_tones(parse_chord(bar.chord))
        for a_notes, b_notes in combinations(_melodic(bar).values(), 2):
            for a in a_notes:
                for b in b_notes:
                    if not _overlaps(a, b):
                        continue
                    total += 1
                    both_chord_tones = a.pitch % 12 in tones and b.pitch % 12 in tones
                    clashes += (
                        abs(a.pitch - b.pitch) % 12 in CLASH_INTERVALS and not both_chord_tones
                    )
    return _ratio(clashes, total)


def register_overlap(song: Song, a: Instrument, b: Instrument) -> float | None:
    """Shared fraction of two parts' pitch spans (intersection over union)."""
    spans: list[tuple[int, int]] = []
    for instrument in (a, b):
        pitches = [n.pitch for bar in song.bars if instrument in bar.parts
                   for n in bar.parts[instrument].notes]
        if not pitches:
            return None
        spans.append((min(pitches), max(pitches)))
    (lo_a, hi_a), (lo_b, hi_b) = spans
    shared = min(hi_a, hi_b) - max(lo_a, lo_b) + 1
    return max(0, shared) / (max(hi_a, hi_b) - min(lo_a, lo_b) + 1)


def groove_consistency(song: Song, instrument: Instrument) -> float | None:
    """Mean Jaccard similarity of onset-step sets between adjacent bars."""
    steps = steps_per_bar(song.time_signature)
    patterns = [
        {round(_step(n, steps)) for n in bar.parts[instrument].notes}
        if instrument in bar.parts else set()
        for bar in song.bars
    ]
    scores = [len(x & y) / len(x | y) for x, y in zip(patterns, patterns[1:]) if x and y]
    return sum(scores) / len(scores) if scores else None


def empty_beat_rate(song: Song) -> float | None:
    """Fraction of written beats (6 in 6/8, 7 in 7/8) where nobody starts a note."""
    beats, _ = parse_time_signature(song.time_signature)
    empty = 0
    for bar in song.bars:
        struck = {int(n.start * beats) for part in bar.parts.values() for n in part.notes}
        empty += beats - len(struck)
    return _ratio(empty, beats * len(song.bars))


def pitch_in_scale_rate(song: Song) -> float | None:
    """Fraction of non-drum notes inside the scale of their bar's chord."""
    hits = total = 0
    for bar in song.bars:
        scale = scale_for(parse_chord(bar.chord))
        if not scale:
            continue
        for notes in _melodic(bar).values():
            total += len(notes)
            hits += sum(n.pitch % 12 in scale for n in notes)
    return _ratio(hits, total)


def ensemble_report(song: Song) -> dict[str, Any]:
    """Every metric for one song, keyed by name."""
    played = [i for i in Instrument if any(i in bar.parts for bar in song.bars)]
    melodic = [i for i in played if i is not Instrument.DRUMS]
    bass = lowest_part(song)
    return {
        "on_grid_rate": on_grid_rate(song),
        "kick_bass_lock": kick_bass_lock(song, bass) if bass else None,
        "chord_tone_on_strong_beat_rate": chord_tone_on_strong_beat_rate(song),
        "clash_rate": clash_rate(song),
        "register_overlap": {
            f"{a}/{b}": register_overlap(song, a, b) for a, b in combinations(melodic, 2)
        },
        "groove_consistency": {i.value: groove_consistency(song, i) for i in played},
        "empty_beat_rate": empty_beat_rate(song),
        "pitch_in_scale_rate": pitch_in_scale_rate(song),
    }
