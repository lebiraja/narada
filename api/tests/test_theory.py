"""Chord symbols in, real pitch sets out. Wrong here means wrong notes everywhere."""

import pytest

from app.core.theory import (
    Chord,
    Quality,
    avoid_tones,
    chord_tones,
    describe_harmony,
    parse_chord,
    pitch_names,
    register_for,
    scale_for,
    tension_tones,
)
from app.core.schema import Instrument


class TestParsing:
    @pytest.mark.parametrize(
        ("symbol", "root", "quality"),
        [
            ("C", 0, Quality.MAJOR),
            ("Am", 9, Quality.MINOR),
            ("F#m", 6, Quality.MINOR),
            ("Bb", 10, Quality.MAJOR),
            ("Db", 1, Quality.MAJOR),
            ("G7", 7, Quality.DOMINANT),
            ("Cmaj7", 0, Quality.MAJOR7),
            ("Dm7", 2, Quality.MINOR7),
            ("Bm7b5", 11, Quality.HALF_DIM),
            ("Cdim", 0, Quality.DIMINISHED),
            ("Caug", 0, Quality.AUGMENTED),
            ("Csus4", 0, Quality.SUS4),
            ("Csus2", 0, Quality.SUS2),
            ("C6", 0, Quality.MAJOR6),
            ("Am9", 9, Quality.MINOR7),  # a minor 7th carrying a 9th
            ("C13", 0, Quality.DOMINANT),
        ],
    )
    def test_reads_common_symbols(self, symbol, root, quality):
        chord = parse_chord(symbol)

        assert chord.root == root
        assert chord.quality is quality

    def test_reads_extensions(self):
        assert parse_chord("Am9").extensions == [9]
        assert parse_chord("C13").extensions == [13]
        assert parse_chord("Cmaj7#11").extensions == [11]

    def test_reads_a_slash_bass(self):
        chord = parse_chord("C/E")

        assert chord.root == 0
        assert chord.bass == 4

    def test_bass_defaults_to_the_root(self):
        assert parse_chord("Am").bass == 9

    def test_unparseable_symbols_fall_back_rather_than_raise(self):
        chord = parse_chord("N.C.")

        assert chord is None

    def test_nonsense_falls_back(self):
        assert parse_chord("wibble") is None
        assert parse_chord("") is None


class TestChordTones:
    def test_major_triad(self):
        assert chord_tones(parse_chord("C")) == {0, 4, 7}

    def test_minor_triad(self):
        assert chord_tones(parse_chord("Am")) == {9, 0, 4}

    def test_dominant_seventh(self):
        assert chord_tones(parse_chord("G7")) == {7, 11, 2, 5}

    def test_major_seventh(self):
        assert chord_tones(parse_chord("Cmaj7")) == {0, 4, 7, 11}

    def test_minor_ninth_includes_the_ninth(self):
        assert chord_tones(parse_chord("Am9")) == {9, 0, 4, 7, 11}

    def test_half_diminished(self):
        assert chord_tones(parse_chord("Bm7b5")) == {11, 2, 5, 9}

    def test_sus4_replaces_the_third(self):
        tones = chord_tones(parse_chord("Csus4"))

        assert 5 in tones
        assert 4 not in tones

    def test_sixth_chord(self):
        assert chord_tones(parse_chord("C6")) == {0, 4, 7, 9}


class TestScales:
    def test_minor_seventh_gets_dorian(self):
        assert scale_for(parse_chord("Dm7")) == {2, 4, 5, 7, 9, 11, 0}

    def test_dominant_gets_mixolydian(self):
        assert scale_for(parse_chord("G7")) == {7, 9, 11, 0, 2, 4, 5}

    def test_major_seventh_gets_ionian(self):
        assert scale_for(parse_chord("Cmaj7")) == {0, 2, 4, 5, 7, 9, 11}

    def test_half_diminished_gets_locrian(self):
        assert scale_for(parse_chord("Bm7b5")) == {11, 0, 2, 4, 5, 7, 9}

    def test_every_chord_tone_is_in_its_scale(self):
        for symbol in ("C", "Am", "G7", "Cmaj7", "Dm7", "Bm7b5", "Am9", "Csus4", "F#m"):
            chord = parse_chord(symbol)
            assert chord_tones(chord) <= scale_for(chord), symbol


class TestColour:
    def test_the_flat_sixth_is_an_avoid_note_over_a_minor_ninth(self):
        assert 5 in avoid_tones(parse_chord("Am9"))

    def test_the_fourth_is_an_avoid_note_over_a_major_seventh(self):
        assert 5 in avoid_tones(parse_chord("Cmaj7"))

    def test_tensions_are_in_the_scale_but_not_the_chord(self):
        chord = parse_chord("Dm7")
        tensions = tension_tones(chord)

        assert tensions <= scale_for(chord)
        assert not (tensions & chord_tones(chord))

    def test_avoid_notes_are_never_offered_as_tensions(self):
        for symbol in ("Am9", "Cmaj7", "G7", "Dm7"):
            chord = parse_chord(symbol)
            assert not (tension_tones(chord) & avoid_tones(chord)), symbol


class TestPitchNames:
    def test_renders_pitch_classes_as_names(self):
        assert pitch_names({0, 4, 7}) == "C E G"

    def test_orders_from_c_by_default(self):
        assert pitch_names({9, 0, 4}) == "C E A"

    def test_orders_from_a_root_when_given_one(self):
        assert pitch_names({9, 0, 4}, root=9) == "A C E"

    def test_handles_an_empty_set(self):
        assert pitch_names(set()) == "—"


class TestRegisters:
    def test_each_player_gets_its_own_slice(self):
        slices = {i: register_for(i) for i in Instrument}

        assert slices[Instrument.KEYS][0] < slices[Instrument.FLUTE][0]
        assert slices[Instrument.FLUTE][1] > slices[Instrument.GUITAR][1]

    def test_a_register_sits_inside_the_instrument_range(self):
        from app.core.schema import RANGES

        for instrument in Instrument:
            lo, hi = register_for(instrument)
            rlo, rhi = RANGES[instrument]
            assert rlo <= lo < hi <= rhi, instrument

    def test_a_soloist_gets_a_wider_register(self):
        normal = register_for(Instrument.VIOLIN)
        solo = register_for(Instrument.VIOLIN, soloing=True)

        assert (solo[1] - solo[0]) > (normal[1] - normal[0])

    def test_drums_are_left_alone(self):
        from app.core.schema import RANGES

        assert register_for(Instrument.DRUMS) == RANGES[Instrument.DRUMS]


class TestHarmonyBriefing:
    def test_describes_a_chord_in_terms_a_player_can_use(self):
        brief = describe_harmony("Am9", Instrument.VIOLIN)

        assert "A C E G B" in brief  # read from the root, as a player would
        assert "Scale" in brief
        assert "Avoid" in brief

    def test_says_so_plainly_when_there_is_no_chord(self):
        brief = describe_harmony("N.C.", Instrument.FLUTE)

        assert "no fixed harmony" in brief.lower()

    def test_mentions_the_register(self):
        assert "register" in describe_harmony("Dm7", Instrument.KEYS).lower()

    def test_drums_get_no_harmony_lecture(self):
        assert describe_harmony("Am9", Instrument.DRUMS) == ""


class TestHeavySymbols:
    """Power chords are the commonest symbol in heavy music and used to fail."""

    @pytest.mark.parametrize("symbol", ["E5", "A5", "Bb5", "C#5"])
    def test_power_chords_parse(self, symbol):
        assert parse_chord(symbol).quality is Quality.POWER

    def test_a_power_chord_is_root_and_fifth_only(self):
        assert chord_tones(parse_chord("E5")) == {4, 11}

    def test_a_power_chord_states_no_third(self):
        tones = chord_tones(parse_chord("E5"))

        assert 7 not in tones  # no G, no major third either
        assert 8 not in tones

    def test_a_power_chord_forbids_nothing(self):
        """With no third stated, neither third is wrong."""
        assert avoid_tones(parse_chord("A5")) == set()

    def test_a_power_chord_takes_no_extensions(self):
        assert parse_chord("E5").extensions == []

    @pytest.mark.parametrize(
        ("symbol", "quality"),
        [
            ("Cadd9", Quality.MAJOR),
            ("C-", Quality.MINOR),
            ("Cø", Quality.HALF_DIM),
        ],
    )
    def test_other_common_shorthands(self, symbol, quality):
        assert parse_chord(symbol).quality is quality

    def test_add9_contributes_its_ninth(self):
        assert 2 in chord_tones(parse_chord("Cadd9"))

    def test_a_power_chord_scale_is_playable(self):
        chord = parse_chord("E5")

        assert chord_tones(chord) <= scale_for(chord)
        assert len(scale_for(chord)) >= 7
