"""How each instrument can change its voice, and what that means downstream.

One table, three consumers: the prompts describe the options to the player,
the MIDI exporter maps them to real soundfont presets, and the browser
approximates them with envelope and filter settings.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.schema import Instrument


class Articulation(StrEnum):
    # Strings
    PIZZ = "pizz"
    TREMOLO = "tremolo"
    SUSTAIN = "sustain"
    HARP = "harp"
    # Guitar
    PALM_MUTE = "palm_mute"
    HARMONICS = "harmonics"
    NYLON = "nylon"
    TWELVE_STRING = "twelve_string"
    CLEAN = "clean"
    OVERDRIVE = "overdrive"
    # Winds
    RECORDER = "recorder"
    PAN_FLUTE = "pan_flute"
    # Keys
    RHODES = "rhodes"
    FM_PIANO = "fm_piano"
    HARPSICHORD = "harpsichord"
    BRIGHT = "bright"
    # Universal shaping
    STACCATO = "staccato"
    ACCENT = "accent"
    GHOST = "ghost"


@dataclass(frozen=True)
class Voice:
    """A playable articulation and how to realise it."""

    articulation: Articulation
    description: str
    #: General MIDI bank and program, when this articulation is a different patch.
    bank: int | None = None
    program: int | None = None
    #: Velocity scaling, for articulations that are about attack rather than timbre.
    velocity_scale: float = 1.0
    #: Duration scaling, e.g. staccato clipping a note short.
    duration_scale: float = 1.0
    #: Semitone shift, for guitar harmonics sounding an octave up.
    transpose: int = 0
    #: Browser approximation: oscillator plus envelope, matching core.schema.Patch.
    browser: dict[str, float | str] | None = None


#: Everything a player may ask for, per instrument. The first entry of each
#: list is that instrument's default voice.
VOICES: dict[Instrument, tuple[Voice, ...]] = {
    Instrument.VIOLIN: (
        Voice(
            Articulation.SUSTAIN,
            "normal bowing, singing tone",
            bank=0,
            program=40,
            browser={"oscillator": "fmsine", "attack": 0.09, "decay": 0.2,
                     "sustain": 0.85, "release": 0.7, "filter_freq": 7000},
        ),
        Voice(
            Articulation.PIZZ,
            "plucked, short and dry — good for rhythm or a dry answer",
            bank=0,
            program=45,
            duration_scale=0.35,
            browser={"oscillator": "triangle", "attack": 0.002, "decay": 0.18,
                     "sustain": 0.0, "release": 0.25, "filter_freq": 5000},
        ),
        Voice(
            Articulation.TREMOLO,
            "fast repeated bowing — tension, shimmer, a held threat",
            bank=0,
            program=44,
            browser={"oscillator": "sawtooth", "attack": 0.05, "decay": 0.1,
                     "sustain": 0.8, "release": 0.4, "filter_freq": 6000},
        ),
        Voice(
            Articulation.HARP,
            "harp — rolled chords and arpeggios, no bow at all",
            bank=0,
            program=46,
            duration_scale=0.8,
            browser={"oscillator": "triangle", "attack": 0.003, "decay": 0.6,
                     "sustain": 0.1, "release": 1.2, "filter_freq": 8000},
        ),
    ),
    Instrument.FLUTE: (
        Voice(
            Articulation.SUSTAIN,
            "normal flute tone",
            bank=0,
            program=73,
            browser={"oscillator": "sine", "attack": 0.06, "decay": 0.1,
                     "sustain": 0.9, "release": 0.4, "filter_freq": 11000},
        ),
        Voice(
            Articulation.RECORDER,
            "recorder — woodier, older, plainer",
            bank=0,
            program=74,
            browser={"oscillator": "sine", "attack": 0.04, "decay": 0.1,
                     "sustain": 0.85, "release": 0.3, "filter_freq": 9000},
        ),
        Voice(
            Articulation.PAN_FLUTE,
            "pan flute — breathy and hollow, carries a folk melody",
            bank=0,
            program=75,
            browser={"oscillator": "sine", "attack": 0.11, "decay": 0.15,
                     "sustain": 0.8, "release": 0.6, "filter_freq": 7000},
        ),
    ),
    Instrument.GUITAR: (
        Voice(
            Articulation.CLEAN,
            "steel-string, ringing",
            bank=0,
            program=25,
            browser={"oscillator": "sawtooth", "attack": 0.004, "decay": 0.3,
                     "sustain": 0.2, "release": 0.6, "filter_freq": 5000},
        ),
        Voice(
            Articulation.NYLON,
            "nylon-string — soft, classical, fingerpicked",
            bank=0,
            program=24,
            browser={"oscillator": "triangle", "attack": 0.006, "decay": 0.35,
                     "sustain": 0.15, "release": 0.7, "filter_freq": 4000},
        ),
        Voice(
            Articulation.PALM_MUTE,
            "palm-muted — percussive, tight, sits under everything",
            bank=0,
            program=28,
            duration_scale=0.4,
            browser={"oscillator": "square", "attack": 0.002, "decay": 0.12,
                     "sustain": 0.0, "release": 0.15, "filter_freq": 1800},
        ),
        Voice(
            Articulation.HARMONICS,
            "harmonics — bell-like, sounds an octave above where you write it",
            bank=0,
            program=31,
            transpose=12,
            browser={"oscillator": "sine", "attack": 0.005, "decay": 0.5,
                     "sustain": 0.1, "release": 1.0, "filter_freq": 9000},
        ),
        Voice(
            Articulation.TWELVE_STRING,
            "12-string — wide and chiming, good for a chorus",
            bank=8,
            program=25,
            browser={"oscillator": "sawtooth", "attack": 0.005, "decay": 0.4,
                     "sustain": 0.25, "release": 0.8, "filter_freq": 6000},
        ),
        Voice(
            Articulation.OVERDRIVE,
            "overdriven — dirty, sustaining, for a loud section only",
            bank=0,
            program=29,
            browser={"oscillator": "sawtooth", "attack": 0.003, "decay": 0.2,
                     "sustain": 0.6, "release": 0.5, "filter_freq": 3500},
        ),
    ),
    Instrument.KEYS: (
        Voice(
            Articulation.SUSTAIN,
            "grand piano",
            bank=0,
            program=0,
            browser={"oscillator": "triangle", "attack": 0.005, "decay": 0.4,
                     "sustain": 0.3, "release": 1.2, "filter_freq": 9000},
        ),
        Voice(
            Articulation.RHODES,
            "Rhodes electric — warm, bell-like, sits behind a soloist",
            bank=0,
            program=4,
            browser={"oscillator": "fmsine", "attack": 0.01, "decay": 0.5,
                     "sustain": 0.4, "release": 1.4, "filter_freq": 6000},
        ),
        Voice(
            Articulation.FM_PIANO,
            "FM electric piano — glassier than the Rhodes",
            bank=0,
            program=5,
            browser={"oscillator": "fmsine", "attack": 0.008, "decay": 0.4,
                     "sustain": 0.35, "release": 1.0, "filter_freq": 8000},
        ),
        Voice(
            Articulation.HARPSICHORD,
            "harpsichord — plucked and brittle, no dynamics to speak of",
            bank=0,
            program=6,
            duration_scale=0.6,
            browser={"oscillator": "square", "attack": 0.002, "decay": 0.25,
                     "sustain": 0.0, "release": 0.4, "filter_freq": 7000},
        ),
        Voice(
            Articulation.BRIGHT,
            "bright grand — cuts through a dense arrangement",
            bank=0,
            program=1,
            browser={"oscillator": "triangle", "attack": 0.004, "decay": 0.35,
                     "sustain": 0.3, "release": 1.0, "filter_freq": 11000},
        ),
    ),
    Instrument.DRUMS: (
        Voice(Articulation.SUSTAIN, "normal stroke"),
        Voice(Articulation.GHOST, "ghost note — barely there, fills the gaps",
              velocity_scale=0.3),
        Voice(Articulation.ACCENT, "accented — the stroke you lean on",
              velocity_scale=1.25),
    ),
}

#: Shaping articulations any melodic instrument may use on top of its voice.
UNIVERSAL: tuple[Voice, ...] = (
    Voice(Articulation.STACCATO, "clipped short, detached", duration_scale=0.4),
    Voice(Articulation.ACCENT, "leaned on, louder than its neighbours",
          velocity_scale=1.25),
    Voice(Articulation.GHOST, "almost silent, a shadow of a note",
          velocity_scale=0.3),
)


def voice_for(instrument: Instrument, articulation: str | None) -> Voice:
    """The Voice a note should be played with. Falls back to the default."""
    default = VOICES[instrument][0]
    if not articulation:
        return default

    wanted = articulation.strip().lower()
    for voice in VOICES[instrument]:
        if voice.articulation == wanted:
            return voice
    for voice in UNIVERSAL:
        if voice.articulation == wanted:
            # A shaping articulation keeps the instrument's default timbre.
            return Voice(
                voice.articulation,
                voice.description,
                bank=default.bank,
                program=default.program,
                velocity_scale=voice.velocity_scale,
                duration_scale=voice.duration_scale,
                browser=default.browser,
            )
    return default


def allowed(instrument: Instrument) -> list[str]:
    """Every articulation this instrument accepts, for prompts and validation."""
    own = [v.articulation.value for v in VOICES[instrument]]
    if instrument is Instrument.DRUMS:
        return own
    return own + [v.articulation.value for v in UNIVERSAL if v.articulation.value not in own]


def describe_voices(instrument: Instrument) -> str:
    """The articulation menu a player sees in its prompt."""
    lines = [f'  "{v.articulation.value}" — {v.description}' for v in VOICES[instrument]]
    if instrument is not Instrument.DRUMS:
        lines += [
            f'  "{v.articulation.value}" — {v.description}'
            for v in UNIVERSAL
            if v.articulation.value not in {x.articulation.value for x in VOICES[instrument]}
        ]
    return "\n".join(lines)
