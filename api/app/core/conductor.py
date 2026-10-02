"""The conductor: deterministic clean-up of a bar after the players write it,
and a critic that turns ensemble metrics into notes a player can act on.

Pure functions. `conduct` never mutates its input and returns a new Bar.
Rules run in a fixed order so a second pass changes nothing on a clean bar:

    quantize -> register -> harmony -> dedupe -> clash -> dynamics

Dynamics is the one exception to idempotence: a soloist cue scales the
other parts' velocities every time it is applied.
"""

from dataclasses import dataclass
from itertools import combinations

from app.core.meter import beats_per_bar, steps_per_bar
from app.core.metrics import (
    STRONG_BEATS,
    chord_tone_on_strong_beat_rate,
    clash_rate,
    groove_consistency,
    lowest_part,
    register_overlap,
)
from app.core.schema import RANGES, Bar, BarPart, Feel, Instrument, Note, SectionCue, Song
from app.core.theory import chord_tones, parse_chord, register_for, tension_tones

#: A melodic onset is only pulled onto the grid when it is this close, in steps.
SOFT_SNAP = 1 / 3
#: Who keeps their note when two parts clash; the cue's soloist outranks all.
PRIORITY = (Instrument.VIOLIN, Instrument.FLUTE, Instrument.KEYS, Instrument.GUITAR)
#: Most notes an instrument may sound at once.
POLYPHONY = {Instrument.FLUTE: 1, Instrument.VIOLIN: 1}
DEFAULT_POLYPHONY = 4
#: Velocity scale for everyone who is not soloing.
ACCOMPANY = 0.85
#: A flautist has to breathe: longest unbroken run, in quarter-note beats.
FLUTE_BREATH_BEATS = 3

CLASH_THRESHOLD = 0.08
STRONG_BEAT_FLOOR = 0.6
OVERLAP_CEILING = 0.5
GROOVE_FLOOR = 0.3

_EPS = 1e-9


@dataclass(frozen=True)
class ConductorConfig:
    quantize: bool = True
    dedupe: bool = True
    harmony: bool = True
    clash: bool = True
    register: bool = True
    dynamics: bool = True


@dataclass(frozen=True)
class Finding:
    instrument: Instrument | None
    bars: tuple[int, ...]
    metric: str
    message: str


def _end(note: Note) -> float:
    return note.start + note.dur


def _overlaps(a: Note, b: Note) -> bool:
    return a.start < _end(b) - _EPS and b.start < _end(a) - _EPS


def _window(instrument: Instrument, cue: SectionCue | None) -> tuple[int, int]:
    return register_for(instrument, soloing=cue is not None and cue.soloist is instrument)


def _quantize(
    notes: list[Note], steps: int, *, hard: bool
) -> list[Note]:
    out: list[Note] = []
    for note in notes:
        position = note.start * steps
        start = note.start
        if hard or abs(position - round(position)) <= SOFT_SNAP:
            start = round(position) / steps
        if start >= 1.0:
            continue
        dur = min(max(1, round(note.dur * steps)) / steps, 4.0)
        out.append(note.model_copy(update={"start": start, "dur": dur}))
    return out


def _harmonize(notes: list[Note], chord: str, window: tuple[int, int], steps: int) -> list[Note]:
    parsed = parse_chord(chord)
    if parsed is None:
        return notes
    tones = chord_tones(parsed)
    allowed = tones | tension_tones(parsed)
    lo, hi = window
    out: list[Note] = []
    for note in notes:
        strong = any(abs(note.start - beat) * steps <= _EPS for beat in STRONG_BEATS)
        if strong and note.pitch % 12 not in allowed:
            candidates = [
                note.pitch + d for d in (-1, 1, -2, 2)
                if (note.pitch + d) % 12 in tones and lo <= note.pitch + d <= hi
            ]
            if candidates:
                note = note.model_copy(update={"pitch": candidates[0]})
        out.append(note)
    return out


def _into_register(notes: list[Note], window: tuple[int, int]) -> list[Note]:
    lo, hi = window
    out: list[Note] = []
    for note in notes:
        pitch = note.pitch
        while pitch < lo:
            pitch += 12
        while pitch > hi:
            pitch -= 12
        if lo <= pitch <= hi:
            out.append(note.model_copy(update={"pitch": pitch}))
    return out


def _dedupe(notes: list[Note]) -> list[Note]:
    """Drop exact repeats; cut a held note off where the same pitch strikes again."""
    ordered = sorted(notes, key=lambda n: (n.pitch, n.start, -n.velocity))
    out: list[Note] = []
    for note in ordered:
        if out and out[-1].pitch == note.pitch:
            held = out[-1]
            if abs(held.start - note.start) <= _EPS:
                continue
            if _end(held) > note.start + _EPS:
                out[-1] = held.model_copy(update={"dur": note.start - held.start})
        out.append(note)
    return sorted(out, key=lambda n: (n.start, n.pitch))


def _cap_polyphony(notes: list[Note], cap: int) -> list[Note]:
    kept: list[Note] = []
    for note in sorted(notes, key=lambda n: -n.velocity):
        sounding = [k for k in kept if _overlaps(k, note)]
        points = [note.start] + [k.start for k in sounding if k.start > note.start]
        if all(sum(k.start <= p + _EPS and _end(k) > p + _EPS for k in sounding) < cap
               for p in points):
            kept.append(note)
    return sorted(kept, key=lambda n: (n.start, n.pitch))


def _breathe(notes: list[Note], limit: float, step: float) -> list[Note]:
    """Shorten the longest note of any unbroken run longer than `limit` by a step,
    dropping it when it is already a single step, until every run fits."""
    notes = sorted(notes, key=lambda n: n.start)
    while True:
        runs: list[list[int]] = []
        for i, note in enumerate(notes):
            if runs and abs(note.start - _end(notes[runs[-1][-1]])) <= _EPS:
                runs[-1].append(i)
            else:
                runs.append([i])
        long_run = next(
            (r for r in runs if _end(notes[r[-1]]) - notes[r[0]].start > limit + _EPS), None
        )
        if long_run is None:
            return notes
        longest = max(long_run, key=lambda i: notes[i].dur)
        dur = notes[longest].dur - step
        if dur > _EPS:
            notes[longest] = notes[longest].model_copy(update={"dur": dur})
        else:
            del notes[longest]


def _rank(instrument: Instrument, cue: SectionCue | None) -> int:
    if cue is not None and cue.soloist is instrument:
        return -1
    return PRIORITY.index(instrument) if instrument in PRIORITY else len(PRIORITY)


def _clashes(a: Note, b: Note, tones: set[int]) -> bool:
    interval = abs(a.pitch - b.pitch) % 12
    a_tone, b_tone = a.pitch % 12 in tones, b.pitch % 12 in tones
    if interval in (1, 11):
        return not (a_tone and b_tone)
    return interval == 6 and not a_tone and not b_tone


def conduct(
    bar: Bar,
    *,
    feel: Feel,
    previous: Bar | None = None,
    cue: SectionCue | None = None,
    config: ConductorConfig = ConductorConfig(),
) -> Bar:
    """Return a cleaned copy of `bar`. `previous` steadies which part counts as the bass."""
    steps = steps_per_bar(feel.time_signature)
    parts = {i: list(p.notes) for i, p in bar.parts.items()}
    melodic = [i for i in parts if i is not Instrument.DRUMS]
    context = [b for b in (previous, bar) if b is not None]
    bass = lowest_part(Song(title="bar", key="C", tempo=120, bars=context))

    for instrument in parts:
        window = _window(instrument, cue)
        if config.quantize:
            hard = instrument is Instrument.DRUMS or instrument is bass
            parts[instrument] = _quantize(parts[instrument], steps, hard=hard)
        if instrument is Instrument.DRUMS:
            continue
        if config.register:
            parts[instrument] = _into_register(parts[instrument], window)
        if config.harmony:
            parts[instrument] = _harmonize(parts[instrument], bar.chord, window, steps)

    if config.dedupe:
        parts = {i: _dedupe(notes) for i, notes in parts.items()}
        for a, b in combinations(melodic, 2):
            upper, lower = sorted((a, b), key=lambda i: -sum(_window(i, cue)))
            onsets = {(n.pitch, n.start) for n in parts[lower]}
            lo, hi = _window(upper, cue) if config.register else RANGES[upper]
            moved: list[Note] = []
            for note in parts[upper]:
                if (note.pitch, note.start) in onsets:
                    if note.pitch + 12 > hi:
                        continue
                    note = note.model_copy(update={"pitch": note.pitch + 12})
                moved.append(note)
            parts[upper] = _dedupe(moved)

    if config.clash:
        tones = chord_tones(parse_chord(bar.chord))
        ranked = sorted(melodic, key=lambda i: _rank(i, cue))
        for n, instrument in enumerate(ranked):
            above = [k for i in ranked[:n] for k in parts[i]]
            parts[instrument] = [
                note for note in parts[instrument]
                if not any(_overlaps(note, k) and _clashes(note, k, tones) for k in above)
            ]

    if config.dynamics:
        for instrument in melodic:
            notes = _cap_polyphony(
                parts[instrument], POLYPHONY.get(instrument, DEFAULT_POLYPHONY)
            )
            if cue is not None and cue.soloist is not None and instrument is not cue.soloist:
                notes = [
                    n.model_copy(update={"vel": max(1, round(n.velocity * ACCOMPANY))})
                    for n in notes
                ]
            if instrument is Instrument.FLUTE:
                limit = FLUTE_BREATH_BEATS / beats_per_bar(feel.time_signature)
                notes = _breathe(notes, limit, 1 / steps)
            parts[instrument] = notes

    return bar.model_copy(
        update={
            "parts": {
                i: p.model_copy(update={"notes": parts[i]}) for i, p in bar.parts.items()
            }
        }
    )


def _span(bars: list[int]) -> str:
    """[5, 6, 9] -> "bars 5-6, 9"."""
    groups: list[list[int]] = []
    for index in sorted(bars):
        if groups and index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    text = ", ".join(f"{g[0]}" if len(g) == 1 else f"{g[0]}-{g[-1]}" for g in groups)
    return f"bar{'s' if len(bars) > 1 else ''} {text}"


def _only(bar: Bar, instruments: set[Instrument]) -> Bar:
    return bar.model_copy(
        update={"parts": {i: p for i, p in bar.parts.items() if i in instruments}}
    )


def critique(bars: list[Bar], feel: Feel) -> list[Finding]:
    """Read the band's last few bars and say, per player, what to fix."""

    def song(selection: list[Bar]) -> Song:
        return Song(
            title="critique",
            key=feel.key or "C",
            tempo=feel.tempo or 120,
            time_signature=feel.time_signature,
            bars=selection,
        )

    played = [i for i in Instrument if any(i in b.parts and b.parts[i].notes for b in bars)]
    melodic = [i for i in played if i is not Instrument.DRUMS]
    indices = tuple(b.index for b in bars)
    findings: list[Finding] = []

    for a, b in combinations(melodic, 2):
        loser = max((a, b), key=lambda i: _rank(i, None))
        other = a if loser is b else b
        hit = [
            bar.index for bar in bars
            if (rate := clash_rate(song([_only(bar, {a, b})]))) is not None
            and rate > CLASH_THRESHOLD
        ]
        if hit:
            findings.append(Finding(
                loser, tuple(hit), "clash_rate",
                f"You're grinding a half-step against the {other} in {_span(hit)} — "
                f"find a chord tone or leave space.",
            ))

        overlap = register_overlap(song(bars), a, b)
        if overlap is not None and overlap > OVERLAP_CEILING:
            busier = max(
                (a, b), key=lambda i: sum(len(x.parts[i].notes) for x in bars if i in x.parts)
            )
            quieter = a if busier is b else b
            findings.append(Finding(
                busier, indices, "register_overlap",
                f"You and the {quieter} are crowding the same octave — move up or sit out.",
            ))

    for instrument in melodic:
        hit = [
            bar.index for bar in bars
            if (rate := chord_tone_on_strong_beat_rate(song([_only(bar, {instrument})])))
            is not None and rate < STRONG_BEAT_FLOOR
        ]
        if hit:
            findings.append(Finding(
                instrument, tuple(hit), "chord_tone_on_strong_beat_rate",
                f"Your downbeats miss the chord in {_span(hit)} — land on a chord tone.",
            ))

    bass = lowest_part(song(bars))
    for instrument in [i for i in played if i is Instrument.DRUMS or i is bass]:
        groove = groove_consistency(song(bars), instrument)
        if groove is not None and groove < GROOVE_FLOOR:
            findings.append(Finding(
                instrument, indices, "groove_consistency",
                f"Your pattern changes every bar in {_span(list(indices))} — "
                f"settle on a groove and repeat it.",
            ))

    return findings


def feedback_for(findings: list[Finding], instrument: Instrument) -> str:
    """The critic's notes for one player, ready to drop into a regeneration prompt."""
    return " ".join(f.message for f in findings if f.instrument is instrument)
