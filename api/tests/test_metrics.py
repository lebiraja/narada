import pytest

from app.core.meter import beats_per_bar, parse_time_signature, steps_per_bar
from app.core.metrics import (
    chord_tone_on_strong_beat_rate,
    clash_rate,
    empty_beat_rate,
    ensemble_report,
    groove_consistency,
    kick_bass_lock,
    lowest_part,
    on_grid_rate,
    pitch_in_scale_rate,
    register_overlap,
)
from app.core.schema import Bar, BarPart, Instrument, Note, Song


def _bar(index: int, chord: str, parts: dict[Instrument, list[tuple[int, float, float]]]) -> Bar:
    """Build a bar from (pitch, start, dur) triples per instrument."""
    return Bar(
        index=index,
        chord=chord,
        parts={
            instrument: BarPart(
                instrument=instrument,
                bar=index,
                notes=[Note(pitch=p, start=s, dur=d) for p, s, d in notes],
            )
            for instrument, notes in parts.items()
        },
    )


def _song(*bars: Bar, signature: str = "4/4") -> Song:
    return Song(title="t", key="C", tempo=120, time_signature=signature, bars=list(bars))


@pytest.mark.parametrize(
    ("signature", "expected", "beats", "steps"),
    [
        ("4/4", (4, 4), 4.0, 16),
        ("3/4", (3, 4), 3.0, 12),
        ("6/8", (6, 8), 3.0, 12),
        ("7/8", (7, 8), 3.5, 14),
        ("garbage", (4, 4), 4.0, 16),
    ],
)
def test_meter(signature: str, expected: tuple[int, int], beats: float, steps: int):
    # Arrange / Act
    parsed = parse_time_signature(signature)

    # Assert
    assert parsed == expected
    assert beats_per_bar(signature) == beats
    assert steps_per_bar(signature) == steps


def test_on_grid_rate_counts_onsets_off_the_sixteenth_grid():
    # Arrange: 0.03 of a 16-step bar is half a step late.
    song = _song(_bar(0, "C", {Instrument.KEYS: [(60, 0.0, 0.25), (62, 0.25, 0.25), (64, 0.03, 0.1)]}))

    # Act
    rate = on_grid_rate(song)

    # Assert
    assert rate == pytest.approx(2 / 3)


def test_on_grid_rate_uses_the_meter():
    # Arrange: in 7/8 a step is 1/14 of the bar, which is off the 4/4 grid.
    song = _song(_bar(0, "C", {Instrument.KEYS: [(60, 1 / 14, 0.1)]}), signature="7/8")

    # Act
    rate = on_grid_rate(song)

    # Assert
    assert rate == 1.0


def test_lowest_part_is_the_lowest_sounding_non_drum_part():
    # Arrange
    song = _song(_bar(0, "C", {
        Instrument.DRUMS: [(36, 0.0, 0.1)],
        Instrument.KEYS: [(40, 0.0, 0.5)],
        Instrument.FLUTE: [(72, 0.0, 0.5)],
    }))

    # Act
    bass = lowest_part(song)

    # Assert
    assert bass is Instrument.KEYS


def test_kick_bass_lock_allows_one_step_of_slack():
    # Arrange: kicks on 1 and 3; bass on 1, just after 3, and alone on 4.
    song = _song(_bar(0, "C", {
        Instrument.DRUMS: [(36, 0.0, 0.1), (36, 0.5, 0.1)],
        Instrument.KEYS: [(36, 0.0, 0.25), (43, 0.5 + 1 / 32, 0.25), (40, 0.75, 0.25), (72, 0.75, 0.25)],
    }))

    # Act
    lock = kick_bass_lock(song, Instrument.KEYS)

    # Assert: the high note on 4 is not bass-register, so it is not counted.
    assert lock == pytest.approx(2 / 3)


def test_kick_bass_lock_is_none_without_a_bass_line():
    # Arrange
    song = _song(_bar(0, "C", {Instrument.FLUTE: [(72, 0.0, 0.5)]}))

    # Act / Assert
    assert kick_bass_lock(song, Instrument.FLUTE) is None


def test_chord_tone_on_strong_beat_rate_ignores_weak_beats():
    # Arrange: C on 1 (chord tone), D on 3 (not), C# on 2 (weak, ignored).
    song = _song(_bar(0, "C", {Instrument.KEYS: [(60, 0.0, 0.25), (62, 0.5, 0.25), (61, 0.25, 0.25)]}))

    # Act
    rate = chord_tone_on_strong_beat_rate(song)

    # Assert
    assert rate == 0.5


def test_clash_rate_counts_overlapping_minor_seconds_between_parts():
    # Arrange: keys C and flute C# overlap (clash); guitar E overlaps both
    # without clashing; violin enters after everyone else has stopped.
    song = _song(_bar(0, "C", {
        Instrument.KEYS: [(60, 0.0, 0.5)],
        Instrument.FLUTE: [(73, 0.0, 0.25)],
        Instrument.GUITAR: [(64, 0.0, 0.5)],
        Instrument.VIOLIN: [(66, 0.75, 0.25)],
    }))

    # Act
    rate = clash_rate(song)

    # Assert
    assert rate == pytest.approx(1 / 3)


def test_clash_rate_forgives_a_tritone_inside_the_chord():
    # Arrange: B and F are the third and seventh of G7.
    song = _song(_bar(0, "G7", {Instrument.KEYS: [(59, 0.0, 1.0)], Instrument.FLUTE: [(65, 0.0, 1.0)]}))

    # Act
    rate = clash_rate(song)

    # Assert
    assert rate == 0.0


def test_register_overlap_is_intersection_over_union():
    # Arrange: keys span 48-60, flute 60-72; they share one semitone of 25.
    song = _song(_bar(0, "C", {
        Instrument.KEYS: [(48, 0.0, 0.5), (60, 0.5, 0.5)],
        Instrument.FLUTE: [(60, 0.0, 0.5), (72, 0.5, 0.5)],
    }))

    # Act
    overlap = register_overlap(song, Instrument.KEYS, Instrument.FLUTE)

    # Assert
    assert overlap == pytest.approx(1 / 25)


def test_groove_consistency_compares_adjacent_bars():
    # Arrange: four-on-the-floor twice, then half of it.
    four = [(36, s, 0.1) for s in (0.0, 0.25, 0.5, 0.75)]
    two = [(36, s, 0.1) for s in (0.0, 0.5)]
    song = _song(
        _bar(0, "C", {Instrument.DRUMS: four}),
        _bar(1, "C", {Instrument.DRUMS: four}),
        _bar(2, "C", {Instrument.DRUMS: two}),
    )

    # Act
    consistency = groove_consistency(song, Instrument.DRUMS)

    # Assert: 1.0 then 0.5.
    assert consistency == pytest.approx(0.75)


def test_empty_beat_rate_counts_beats_nobody_strikes():
    # Arrange
    song = _song(_bar(0, "C", {Instrument.KEYS: [(60, 0.0, 0.25)], Instrument.FLUTE: [(72, 0.5, 0.25)]}))

    # Act
    rate = empty_beat_rate(song)

    # Assert
    assert rate == 0.5


def test_pitch_in_scale_rate_skips_no_chord_bars():
    # Arrange: C# is outside C major; the N.C. bar is not judged.
    song = _song(
        _bar(0, "C", {Instrument.KEYS: [(60, 0.0, 0.25), (62, 0.25, 0.25), (61, 0.5, 0.25)]}),
        _bar(1, "N.C.", {Instrument.KEYS: [(61, 0.0, 0.25)]}),
    )

    # Act
    rate = pitch_in_scale_rate(song)

    # Assert
    assert rate == pytest.approx(2 / 3)


def test_ensemble_report_names_every_metric():
    # Arrange
    song = _song(_bar(0, "C", {
        Instrument.DRUMS: [(36, 0.0, 0.1)],
        Instrument.KEYS: [(40, 0.0, 0.5)],
        Instrument.FLUTE: [(72, 0.0, 0.5)],
    }))

    # Act
    report = ensemble_report(song)

    # Assert
    assert report["kick_bass_lock"] == 1.0
    assert set(report["register_overlap"]) == {"keys/flute"}
    assert set(report["groove_consistency"]) == {"drums", "keys", "flute"}
    assert set(report) == {
        "on_grid_rate", "kick_bass_lock", "chord_tone_on_strong_beat_rate", "clash_rate",
        "register_overlap", "groove_consistency", "empty_beat_rate", "pitch_in_scale_rate",
    }
