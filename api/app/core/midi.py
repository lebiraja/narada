"""Render a Song into MIDI — one file per instrument, plus a merged mix."""

import io
import zipfile

import mido

from app.core.schema import BAND, Instrument, Song

TICKS_PER_BEAT = 480
BEATS_PER_BAR = 4

#: General MIDI program numbers, and channel 9 for percussion.
PROGRAMS: dict[Instrument, int] = {
    Instrument.DRUMS: 0,
    Instrument.KEYS: 0,
    Instrument.GUITAR: 27,
    Instrument.FLUTE: 73,
    Instrument.VIOLIN: 40,
}
DRUM_CHANNEL = 9


def _ticks(position_in_bars: float) -> int:
    return round(position_in_bars * BEATS_PER_BAR * TICKS_PER_BEAT)


def instrument_track(song: Song, instrument: Instrument) -> mido.MidiFile:
    """One instrument's part as a standalone MIDI file."""
    midi = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi.tracks.append(track)

    channel = DRUM_CHANNEL if instrument is Instrument.DRUMS else 0
    track.append(mido.MetaMessage("track_name", name=instrument.value, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.tempo), time=0))
    if instrument is not Instrument.DRUMS:
        track.append(mido.Message("program_change", channel=channel, program=PROGRAMS[instrument], time=0))

    events: list[tuple[int, int, int, int]] = []  # (tick, on/off, pitch, velocity)
    for bar in song.bars:
        part = bar.parts.get(instrument)
        if part is None:
            continue
        bar_start = bar.index
        for note in part.notes:
            start = _ticks(bar_start + note.start)
            events.append((start, 1, note.pitch, note.vel))
            events.append((start + max(1, _ticks(note.dur)), 0, note.pitch, 0))

    # Note-offs sort before note-ons at the same tick so repeated pitches retrigger.
    events.sort(key=lambda e: (e[0], e[1]))

    clock = 0
    for tick, on, pitch, velocity in events:
        track.append(
            mido.Message(
                "note_on" if on else "note_off",
                channel=channel,
                note=pitch,
                velocity=velocity,
                time=tick - clock,
            )
        )
        clock = tick

    return midi


def stems_zip(song: Song) -> bytes:
    """All five stems zipped, named after the song."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for instrument in BAND:
            track = io.BytesIO()
            instrument_track(song, instrument).save(file=track)
            archive.writestr(f"{_slug(song.title)}-{instrument.value}.mid", track.getvalue())
    return buffer.getvalue()


def _slug(title: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in title).split()
    return "-".join(words).lower() or "ai-band"
