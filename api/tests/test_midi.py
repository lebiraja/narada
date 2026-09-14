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
from app.core.kit import KIT_PRESETS, Kit
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


def test_drums_select_their_kit():
    """The kit is a percussion preset, so it needs bank 128 and a program."""
    song = make_song()
    song.kit = "brush"

    track = instrument_track(song, Instrument.DRUMS).tracks[0]
    bank = next(m for m in track if m.type == "control_change" and m.control == 0)
    program = next(m for m in track if m.type == "program_change")

    assert bank.value == 1  # bank select MSB 1 -> GM percussion bank 128
    assert program.program == KIT_PRESETS[Kit.BRUSH]


def test_an_unknown_kit_falls_back_to_standard():
    song = make_song()
    song.kit = "bongos-only"

    track = instrument_track(song, Instrument.DRUMS).tracks[0]
    program = next(m for m in track if m.type == "program_change")

    assert program.program == KIT_PRESETS[Kit.STANDARD]


def test_melodic_instruments_get_a_program_change():
    track = instrument_track(make_song(), Instrument.FLUTE).tracks[0]

    assert [m.program for m in track if m.type == "program_change"] == [73]


def test_stems_zip_contains_all_five_instruments():
    archive = zipfile.ZipFile(io.BytesIO(stems_zip(make_song())))

    assert len(archive.namelist()) == 5
    assert "monsoon-line-violin.mid" in archive.namelist()


def test_slug_handles_awkward_titles():
    assert _slug("Monsoon / Line!") == "monsoon-line"
    assert _slug("***") == "narada"


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


def test_articulation_switches_the_patch_and_back():
    """A pizz note plays the pizzicato preset; the next bowed note returns."""
    song = Song(
        title="Articulated",
        key="A minor",
        tempo=90,
        bars=[
            Bar(index=0, chord="Am", parts={
                Instrument.VIOLIN: BarPart(instrument=Instrument.VIOLIN, bar=0, notes=[
                    Note(pitch=69, start=0.0, dur=0.2, vel=90, articulation="pizz"),
                    Note(pitch=72, start=0.5, dur=0.4, vel=90),
                ]),
            }),
        ],
    )

    track = instrument_track(song, Instrument.VIOLIN).tracks[0]
    programs = [m.program for m in track if m.type == "program_change"]

    assert programs == [40, 45, 40]  # violin, pizzicato, back to violin


def test_no_patch_change_when_the_articulation_does_not_need_one():
    song = Song(
        title="Plain",
        key="A minor",
        tempo=90,
        bars=[
            Bar(index=0, chord="Am", parts={
                Instrument.VIOLIN: BarPart(instrument=Instrument.VIOLIN, bar=0, notes=[
                    Note(pitch=69, start=0.0, dur=0.2, vel=90, articulation="staccato"),
                ]),
            }),
        ],
    )

    track = instrument_track(song, Instrument.VIOLIN).tracks[0]

    assert [m.program for m in track if m.type == "program_change"] == [40]


def test_staccato_shortens_the_note():
    def length(articulation: str | None) -> int:
        song = Song(title="T", key="C", tempo=120, bars=[
            Bar(index=0, chord="C", parts={
                Instrument.FLUTE: BarPart(instrument=Instrument.FLUTE, bar=0, notes=[
                    Note(pitch=72, start=0.0, dur=0.5, vel=90, articulation=articulation),
                ]),
            }),
        ])
        track = instrument_track(song, Instrument.FLUTE).tracks[0]
        notes = [m for m in track if m.type in {"note_on", "note_off"}]
        return notes[1].time

    assert length("staccato") < length(None)


def test_accent_and_ghost_scale_velocity():
    def velocity(articulation: str | None) -> int:
        song = Song(title="T", key="C", tempo=120, bars=[
            Bar(index=0, chord="C", parts={
                Instrument.KEYS: BarPart(instrument=Instrument.KEYS, bar=0, notes=[
                    Note(pitch=60, start=0.0, dur=0.25, vel=80, articulation=articulation),
                ]),
            }),
        ])
        track = instrument_track(song, Instrument.KEYS).tracks[0]
        return next(m.velocity for m in track if m.type == "note_on")

    assert velocity("ghost") < velocity(None) < velocity("accent")


def test_guitar_harmonics_sound_an_octave_up():
    song = Song(title="T", key="C", tempo=120, bars=[
        Bar(index=0, chord="C", parts={
            Instrument.GUITAR: BarPart(instrument=Instrument.GUITAR, bar=0, notes=[
                Note(pitch=60, start=0.0, dur=0.25, vel=90, articulation="harmonics"),
            ]),
        }),
    ])

    track = instrument_track(song, Instrument.GUITAR).tracks[0]

    assert next(m.note for m in track if m.type == "note_on") == 72


def test_an_unknown_articulation_plays_the_normal_voice():
    song = Song(title="T", key="C", tempo=120, bars=[
        Bar(index=0, chord="C", parts={
            Instrument.VIOLIN: BarPart(instrument=Instrument.VIOLIN, bar=0, notes=[
                Note(pitch=69, start=0.0, dur=0.25, vel=90, articulation="slap-bass"),
            ]),
        }),
    ])

    track = instrument_track(song, Instrument.VIOLIN).tracks[0]

    assert [m.program for m in track if m.type == "program_change"] == [40]
    assert next(m.note for m in track if m.type == "note_on") == 69
