import pytest
from pydantic import ValidationError

from app.core.schema import Bar, BarPart, Instrument, Note, Patch, SectionCue, Song


def test_note_rejects_start_outside_bar():
    with pytest.raises(ValidationError):
        Note(pitch=60, start=1.0, dur=0.25)


def test_bar_part_drops_out_of_range_pitches():
    part = BarPart(
        instrument=Instrument.FLUTE,
        bar=0,
        notes=[Note(pitch=72, start=0.0, dur=0.25), Note(pitch=30, start=0.5, dur=0.25)],
    )

    assert [n.pitch for n in part.notes] == [72]


def test_bar_part_keeps_in_range_pitches():
    part = BarPart(
        instrument=Instrument.VIOLIN,
        bar=3,
        notes=[Note(pitch=55, start=0.0, dur=0.5), Note(pitch=100, start=0.5, dur=0.5)],
    )

    assert len(part.notes) == 2


def test_patch_rejects_unknown_oscillator():
    with pytest.raises(ValidationError):
        Patch(oscillator="bagpipe", attack=0.1, decay=0.1, sustain=0.5, release=0.3)


def test_section_cue_requires_chords():
    with pytest.raises(ValidationError):
        SectionCue(chords=[])


def test_song_round_trips_through_json():
    song = Song(
        title="Test Jam",
        key="A minor",
        tempo=90,
        bars=[
            Bar(
                index=0,
                chord="Am7",
                parts={
                    Instrument.KEYS: BarPart(
                        instrument=Instrument.KEYS,
                        bar=0,
                        notes=[Note(pitch=69, start=0.0, dur=0.5)],
                    )
                },
            )
        ],
    )

    restored = Song.model_validate_json(song.model_dump_json())

    assert restored.bars[0].parts[Instrument.KEYS].notes[0].pitch == 69
