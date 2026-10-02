import random
from dataclasses import replace

import pytest

from app.core.conductor import (
    ConductorConfig,
    Finding,
    conduct,
    critique,
    feedback_for,
)
from app.core.meter import steps_per_bar
from app.core.schema import RANGES, Bar, BarPart, Feel, Instrument, Note, SectionCue
from app.core.theory import register_for

FEEL = Feel(time_signature="4/4")
OFF = ConductorConfig(
    quantize=False, dedupe=False, harmony=False, clash=False, register=False, dynamics=False
)


def _bar(
    parts: dict[Instrument, list[tuple[int, float, float]]], chord: str = "C", index: int = 0
) -> Bar:
    """Build a bar from (pitch, start, dur) triples per instrument."""
    return Bar(
        index=index,
        chord=chord,
        parts={
            i: BarPart(
                instrument=i,
                bar=index,
                notes=[Note(pitch=p, start=s, dur=d) for p, s, d in notes],
            )
            for i, notes in parts.items()
        },
    )


def _triples(bar: Bar, instrument: Instrument) -> list[tuple[int, float, float]]:
    return [(n.pitch, round(n.start, 6), round(n.dur, 6)) for n in bar.parts[instrument].notes]


def _only(flag: str) -> ConductorConfig:
    return replace(OFF, **{flag: True})


# --- quantize ---------------------------------------------------------------

def test_quantize_hard_snaps_drums_and_rounds_duration() -> None:
    # Arrange
    bar = _bar({Instrument.DRUMS: [(36, 0.03, 0.07)]})

    # Act
    out = conduct(bar, feel=FEEL, config=_only("quantize"))

    # Assert
    assert _triples(out, Instrument.DRUMS) == [(36, 0.0, 0.0625)]


@pytest.mark.parametrize(("start", "expected"), [(0.07, 0.0625), (0.095, 0.095)])
def test_quantize_soft_snaps_melody_only_when_close(start: float, expected: float) -> None:
    # Arrange: guitar is the bass, so flute is the soft-snapped melody
    bar = _bar({Instrument.GUITAR: [(48, 0.0, 0.25)], Instrument.FLUTE: [(76, start, 0.0625)]})

    # Act
    out = conduct(bar, feel=FEEL, config=_only("quantize"))

    # Assert
    assert _triples(out, Instrument.FLUTE)[0][1] == pytest.approx(expected)


def test_quantize_drops_note_snapped_past_the_bar() -> None:
    bar = _bar({Instrument.DRUMS: [(36, 0.99, 0.0625)]})

    out = conduct(bar, feel=FEEL, config=_only("quantize"))

    assert out.parts[Instrument.DRUMS].notes == []


# --- dedupe -----------------------------------------------------------------

def test_dedupe_trims_overlap_and_removes_duplicates() -> None:
    bar = _bar({Instrument.KEYS: [(60, 0.0, 0.5), (60, 0.0, 0.5), (60, 0.25, 0.25)]})

    out = conduct(bar, feel=FEEL, config=_only("dedupe"))

    assert _triples(out, Instrument.KEYS) == [(60, 0.0, 0.25), (60, 0.25, 0.25)]


def test_dedupe_moves_unison_up_an_octave_in_the_higher_player() -> None:
    bar = _bar({Instrument.GUITAR: [(72, 0.0, 0.25)], Instrument.FLUTE: [(72, 0.0, 0.25)]})

    out = conduct(bar, feel=FEEL, config=_only("dedupe"))

    assert _triples(out, Instrument.FLUTE) == [(84, 0.0, 0.25)]
    assert _triples(out, Instrument.GUITAR) == [(72, 0.0, 0.25)]


# --- harmony ----------------------------------------------------------------

def test_harmony_moves_strong_beat_avoid_note_to_chord_tone() -> None:
    # F over C major is the avoid note; nearest chord tone is E
    bar = _bar({Instrument.KEYS: [(65, 0.0, 0.25), (65, 0.25, 0.25)]})

    out = conduct(bar, feel=FEEL, config=_only("harmony"))

    assert _triples(out, Instrument.KEYS) == [(64, 0.0, 0.25), (65, 0.25, 0.25)]


def test_harmony_skips_unparseable_chord() -> None:
    bar = _bar({Instrument.KEYS: [(65, 0.0, 0.25)]}, chord="N.C.")

    out = conduct(bar, feel=FEEL, config=_only("harmony"))

    assert _triples(out, Instrument.KEYS) == [(65, 0.0, 0.25)]


# --- clash ------------------------------------------------------------------

def test_clash_drops_the_lower_priority_note() -> None:
    # B against C, B is not a chord tone of C: guitar loses to violin
    bar = _bar({Instrument.VIOLIN: [(72, 0.0, 0.5)], Instrument.GUITAR: [(59, 0.0, 0.5)]})

    out = conduct(bar, feel=FEEL, config=_only("clash"))

    assert _triples(out, Instrument.GUITAR) == []
    assert _triples(out, Instrument.VIOLIN) == [(72, 0.0, 0.5)]


def test_clash_soloist_outranks_violin() -> None:
    bar = _bar({Instrument.VIOLIN: [(72, 0.0, 0.5)], Instrument.GUITAR: [(59, 0.0, 0.5)]})
    cue = SectionCue(chords=["C"], soloist=Instrument.GUITAR)

    out = conduct(bar, feel=FEEL, cue=cue, config=_only("clash"))

    assert _triples(out, Instrument.VIOLIN) == []


# --- register ---------------------------------------------------------------

def test_register_transposes_by_octaves_into_the_window() -> None:
    lo, hi = register_for(Instrument.FLUTE)
    bar = _bar({Instrument.FLUTE: [(62, 0.0, 0.25)]})

    out = conduct(bar, feel=FEEL, config=_only("register"))

    pitch = out.parts[Instrument.FLUTE].notes[0].pitch
    assert lo <= pitch <= hi and pitch % 12 == 62 % 12


# --- dynamics ---------------------------------------------------------------

def test_dynamics_ducks_accompaniment_under_a_soloist() -> None:
    bar = _bar({Instrument.KEYS: [(60, 0.0, 0.25)], Instrument.FLUTE: [(76, 0.0, 0.25)]})
    cue = SectionCue(chords=["C"], soloist=Instrument.FLUTE)

    out = conduct(bar, feel=FEEL, cue=cue, config=_only("dynamics"))

    assert out.parts[Instrument.KEYS].notes[0].vel == 76
    assert out.parts[Instrument.FLUTE].notes[0].vel is None


def test_dynamics_caps_violin_to_one_voice() -> None:
    bar = _bar({Instrument.VIOLIN: [(72, 0.0, 0.5), (76, 0.0, 0.5)]})

    out = conduct(bar, feel=FEEL, config=_only("dynamics"))

    assert len(out.parts[Instrument.VIOLIN].notes) == 1


def test_dynamics_gives_the_flute_a_breath() -> None:
    bar = _bar({Instrument.FLUTE: [(76, 0.0, 0.5), (79, 0.5, 0.5)]})

    out = conduct(bar, feel=FEEL, config=_only("dynamics"))

    notes = out.parts[Instrument.FLUTE].notes
    assert notes[0].start + notes[0].dur < notes[1].start


# --- flag off is a no-op ----------------------------------------------------

DIRTY = _bar({
    Instrument.DRUMS: [(36, 0.03, 0.07)],
    Instrument.GUITAR: [(59, 0.0, 0.5), (72, 0.0, 0.25)],
    Instrument.KEYS: [(65, 0.0, 0.5), (65, 0.0, 0.5), (60, 0.25, 0.25), (62, 0.25, 0.25),
                      (64, 0.25, 0.25), (67, 0.25, 0.25), (69, 0.25, 0.25)],
    Instrument.VIOLIN: [(72, 0.0, 0.5), (76, 0.0, 0.5)],
    Instrument.FLUTE: [(62, 0.0, 0.5), (72, 0.5, 0.5)],
})


@pytest.mark.parametrize("flag", ["quantize", "dedupe", "harmony", "clash", "register", "dynamics"])
def test_each_rule_off_leaves_the_bar_alone(flag: str) -> None:
    cue = SectionCue(chords=["C"], soloist=Instrument.FLUTE)

    out = conduct(DIRTY, feel=FEEL, cue=cue, config=OFF)
    only_this = conduct(DIRTY, feel=FEEL, cue=cue, config=_only(flag))

    assert out == DIRTY
    assert only_this != DIRTY


# --- whole-bar properties ---------------------------------------------------

def test_conduct_does_not_mutate_input() -> None:
    before = DIRTY.model_copy(deep=True)

    conduct(DIRTY, feel=FEEL)

    assert DIRTY == before


@pytest.mark.parametrize(
    ("signature", "bar"),
    [
        ("4/4", DIRTY),
        ("6/8", _bar({Instrument.DRUMS: [(36, 0.0, 1 / 12), (38, 0.5, 1 / 12)],
                      Instrument.KEYS: [(48, 0.0, 0.5), (64, 1 / 12, 1 / 6)],
                      Instrument.FLUTE: [(79, 0.0, 0.5), (65, 0.5, 0.5)]}, chord="Am7")),
        ("7/8", _bar({Instrument.DRUMS: [(36, 0.02, 1 / 14)],
                      Instrument.GUITAR: [(45, 0.0, 3 / 14), (45, 3 / 14, 2 / 14)],
                      Instrument.VIOLIN: [(70, 0.5, 0.3)]}, chord="G7")),
    ],
)
def test_conduct_is_idempotent(signature: str, bar: Bar) -> None:
    feel = Feel(time_signature=signature)

    once = conduct(bar, feel=feel)

    assert conduct(once, feel=feel) == once


def test_clean_bar_is_unchanged() -> None:
    bar = _bar({
        Instrument.DRUMS: [(36, 0.0, 0.0625), (38, 0.25, 0.0625)],
        Instrument.GUITAR: [(48, 0.0, 0.25), (55, 0.5, 0.25)],
        Instrument.FLUTE: [(76, 0.0, 0.25), (79, 0.5, 0.25)],
    })

    assert conduct(bar, feel=FEEL) == bar


@pytest.mark.parametrize("signature", ["4/4", "6/8", "7/8"])
def test_random_bars_come_out_on_grid_and_in_range(signature: str) -> None:
    rng = random.Random(7)
    feel = Feel(time_signature=signature)
    steps = steps_per_bar(signature)
    for index in range(200):
        bar = _bar(
            {
                i: [
                    (rng.randint(*RANGES[i]), rng.random() * 0.999, rng.uniform(0.01, 1.0))
                    for _ in range(rng.randint(0, 8))
                ]
                for i in rng.sample(list(Instrument), rng.randint(1, 5))
            },
            chord=rng.choice(["C", "Am7", "G7", "F#m7b5", "N.C."]),
            index=index,
        )
        original = {i: [n.start for n in p.notes] for i, p in bar.parts.items()}

        out = conduct(bar, feel=feel)

        for instrument, part in out.parts.items():
            lo, hi = RANGES[instrument]
            soft_misses = {s for s in original[instrument]
                           if abs(s * steps - round(s * steps)) > 1 / 3}
            for note in part.notes:
                assert 0 <= note.start < 1
                assert lo <= note.pitch <= hi
                position = note.start * steps
                assert abs(position - round(position)) < 1e-9 or note.start in soft_misses


# --- critic -----------------------------------------------------------------

def _song_bars(clean: bool) -> list[Bar]:
    if clean:
        return [
            _bar({Instrument.DRUMS: [(36, 0.0, 0.0625), (38, 0.5, 0.0625)],
                  Instrument.GUITAR: [(48, 0.0, 0.5)],
                  Instrument.FLUTE: [(79, 0.0, 0.5)]}, index=i)
            for i in range(4)
        ]
    return [
        _bar({Instrument.DRUMS: [(36, 0.0, 0.0625)] if i % 2 else [(38, 0.25, 0.0625)],
              Instrument.KEYS: [(61, 0.0, 0.5), (66, 0.5, 0.5)],
              Instrument.GUITAR: [(60, 0.0, 0.5), (67, 0.5, 0.5), (62, 0.25, 0.1)]}, index=i)
        for i in range(4)
    ]


def test_critic_flags_a_clashing_crowded_song() -> None:
    findings = critique(_song_bars(clean=False), FEEL)

    metrics = {f.metric for f in findings}
    assert {"clash_rate", "register_overlap", "chord_tone_on_strong_beat_rate",
            "groove_consistency"} <= metrics


def test_critic_is_silent_on_a_clean_song() -> None:
    assert critique(_song_bars(clean=True), FEEL) == []


def test_feedback_for_filters_by_instrument() -> None:
    findings = [
        Finding(Instrument.KEYS, (1,), "clash_rate", "keys note"),
        Finding(Instrument.FLUTE, (1,), "clash_rate", "flute note"),
        Finding(None, (1,), "clash_rate", "band note"),
    ]

    assert feedback_for(findings, Instrument.KEYS) == "keys note"
