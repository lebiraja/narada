import io
import zipfile

import mido

from app.core.midi import (
    TICKS_PER_BEAT,
    _slug,
    beats_per_bar,
    instrument_track,
    parse_time_signature,
    stems_zip,
)
from app.core.schema import Bar, BarPart, Instrument, Note, Song


def make_song() -> Song:
    return Song(
        title="Monsoon Line",
        key="A minor",
        tempo=92,
        bars=[
            Bar(
                index=0,
                chord="Am7",
                parts={
                    Instrument.KEYS: BarPart(
                        instrument=Instrument.KEYS,
                        bar=0,
                        notes=[Note(pitch=69, start=0.0, dur=0.25, vel=100)],
                    ),
                    Instrument.DRUMS: BarPart(
                        instrument=Instrument.DRUMS,
                        bar=0,
                        notes=[Note(pitch=36, start=0.0, dur=0.1, vel=110)],
                    ),
                },
            ),
            Bar(
                index=1,
                chord="Dm7",
                parts={
                    Instrument.KEYS: BarPart(
                        instrument=Instrument.KEYS,
                        bar=1,
                        notes=[Note(pitch=62, start=0.5, dur=0.25, vel=90)],
                    )
                },
            ),
        ],
    )


def test_track_carries_tempo_and_name():
    track = instrument_track(make_song(), Instrument.KEYS).tracks[0]
    metas = {m.type: m for m in track if m.is_meta}

    assert metas["track_name"].name == "keys"
    assert metas["set_tempo"].tempo == mido.bpm2tempo(92)


def test_note_positions_convert_to_ticks():
    track = instrument_track(make_song(), Instrument.KEYS).tracks[0]
    notes = [m for m in track if m.type in {"note_on", "note_off"}]

    # bar 1 at start 0.5 = 6 beats in
    assert sum(m.time for m in notes[:3]) == 6 * TICKS_PER_BEAT


def test_drums_use_the_percussion_channel():
    track = instrument_track(make_song(), Instrument.DRUMS).tracks[0]
    notes = [m for m in track if m.type == "note_on"]

    assert all(m.channel == 9 for m in notes)
    assert not [m for m in track if m.type == "program_change"]


def test_melodic_instruments_get_a_program_change():
    track = instrument_track(make_song(), Instrument.FLUTE).tracks[0]

    assert [m.program for m in track if m.type == "program_change"] == [73]


def test_stems_zip_contains_all_five_instruments():
    archive = zipfile.ZipFile(io.BytesIO(stems_zip(make_song())))

    assert len(archive.namelist()) == 5
    assert "monsoon-line-violin.mid" in archive.namelist()


def test_slug_handles_awkward_titles():
    assert _slug("Monsoon / Line!") == "monsoon-line"
    assert _slug("***") == "ai-band"


def test_parse_time_signature():
    assert parse_time_signature("6/8") == (6, 8)
    assert parse_time_signature("3/4") == (3, 4)


def test_parse_time_signature_falls_back_on_nonsense():
    assert parse_time_signature("swing") == (4, 4)


def test_beats_per_bar_counts_quarter_notes():
    assert beats_per_bar("4/4") == 4
    assert beats_per_bar("6/8") == 3  # six eighths = three quarter-note beats
    assert beats_per_bar("3/4") == 3


def test_track_records_the_time_signature():
    song = make_song()
    song.time_signature = "6/8"

    track = instrument_track(song, Instrument.KEYS).tracks[0]
    meta = next(m for m in track if m.type == "time_signature")

    assert (meta.numerator, meta.denominator) == (6, 8)


def test_compound_meter_shortens_the_bar():
    """A 6/8 bar is three quarter-note beats, not four."""
    song = make_song()
    song.time_signature = "6/8"

    track = instrument_track(song, Instrument.KEYS).tracks[0]
    notes = [m for m in track if m.type in {"note_on", "note_off"}]

    # bar 1 at start 0.5 = 1.5 bars * 3 beats = 4.5 beats in
    assert sum(m.time for m in notes[:3]) == round(4.5 * TICKS_PER_BEAT)
