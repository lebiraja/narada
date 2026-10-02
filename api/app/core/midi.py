"""Render a Song into MIDI — one file per instrument, plus a merged mix."""

import io
import zipfile

import mido

from app.core.articulation import voice_for
from app.core.kit import KIT_PRESETS, Kit
from app.core.meter import beats_per_bar, parse_time_signature
from app.core.schema import BAND, Instrument, Song

TICKS_PER_BEAT = 480

#: General MIDI program numbers, and channel 9 for percussion.
PROGRAMS: dict[Instrument, int] = {
    Instrument.DRUMS: 0,
    Instrument.BASS: 33,
    Instrument.KEYS: 0,
    Instrument.GUITAR: 27,
    Instrument.FLUTE: 73,
    Instrument.VIOLIN: 40,
}
DRUM_CHANNEL = 9


def _ticks(position_in_bars: float, per_bar: float) -> int:
    return round(position_in_bars * per_bar * TICKS_PER_BEAT)


#: Event kinds, ordered so that at the same tick a program change lands before
#: the note that needs it, and a note-off before a note-on that retriggers it.
_PROGRAM, _OFF, _ON = 0, 1, 2


def _kit_preset(song: Song) -> int:
    """The percussion preset for this song's kit, defaulting to standard."""
    try:
        return KIT_PRESETS[Kit(song.kit.strip().lower())]
    except (ValueError, AttributeError):
        return KIT_PRESETS[Kit.STANDARD]


def instrument_track(song: Song, instrument: Instrument) -> mido.MidiFile:
    """One instrument's part as a standalone MIDI file.

    Articulations become real patch changes: a violin marked `pizz` switches
    to the pizzicato preset for those notes and back afterwards, so the
    rendered audio genuinely changes rather than only the metadata.
    """
    midi = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi.tracks.append(track)

    channel = DRUM_CHANNEL if instrument is Instrument.DRUMS else 0
    numerator, denominator = parse_time_signature(song.time_signature)
    per_bar = beats_per_bar(song.time_signature)

    track.append(mido.MetaMessage("track_name", name=instrument.value, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.tempo), time=0))
    track.append(
        mido.MetaMessage(
            "time_signature", numerator=numerator, denominator=denominator, time=0
        )
    )

    if instrument is Instrument.DRUMS:
        # Percussion lives in bank 128; the preset selects the kit.
        track.append(mido.Message("control_change", channel=channel, control=0, value=1, time=0))
        track.append(
            mido.Message("program_change", channel=channel, program=_kit_preset(song), time=0)
        )
    else:
        track.append(
            mido.Message(
                "program_change", channel=channel, program=PROGRAMS[instrument], time=0
            )
        )

    events: list[tuple[int, int, int, int]] = []
    current_program = PROGRAMS[instrument]

    for bar in song.bars:
        part = bar.parts.get(instrument)
        if part is None:
            continue
        for note in part.notes:
            voice = voice_for(instrument, note.articulation)
            start = _ticks(bar.index + note.start, per_bar)

            if (
                instrument is not Instrument.DRUMS
                and voice.program is not None
                and voice.program != current_program
            ):
                events.append((start, _PROGRAM, voice.program, 0))
                current_program = voice.program

            pitch = max(0, min(127, note.pitch + voice.transpose))
            velocity = max(1, min(127, round(note.velocity * voice.velocity_scale)))
            length = max(1, _ticks(note.dur * voice.duration_scale, per_bar))

            events.append((start, _ON, pitch, velocity))
            events.append((start + length, _OFF, pitch, 0))

    events.sort(key=lambda e: (e[0], e[1]))

    clock = 0
    for tick, kind, value, velocity in events:
        if kind == _PROGRAM:
            message = mido.Message(
                "program_change", channel=channel, program=value, time=tick - clock
            )
        else:
            message = mido.Message(
                "note_on" if kind == _ON else "note_off",
                channel=channel,
                note=value,
                velocity=velocity,
                time=tick - clock,
            )
        track.append(message)
        clock = tick

    return midi


def song_to_midi(song: Song) -> mido.MidiFile:
    """Every stem as one type-1 file, each melodic part on its own channel."""
    merged = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    melodic = iter(range(DRUM_CHANNEL))
    for instrument in BAND:
        channel = DRUM_CHANNEL if instrument is Instrument.DRUMS else next(melodic)
        track = instrument_track(song, instrument).tracks[0]
        merged.tracks.append(
            mido.MidiTrack(
                m if m.is_meta else m.copy(channel=channel) for m in track
            )
        )
    return merged


def stems_zip(song: Song) -> bytes:
    """All six stems zipped, named after the song."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for instrument in BAND:
            track = io.BytesIO()
            instrument_track(song, instrument).save(file=track)
            archive.writestr(f"{slug(song.title)}-{instrument.value}.mid", track.getvalue())
    return buffer.getvalue()


def slug(title: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in title).split()
    return "-".join(words).lower() or "narada"
