import pytest

from app.agents.bandleader import Bandleader, chord_for_bar, resolve_soloist
from app.agents.instrument import InstrumentAgent, _render_history
from app.agents.orchestrator import BandOrchestrator
from app.core.schema import BAND, Bar, BarPart, Feel, Instrument, Note, SectionCue
from tests.conftest import FakeProvider


def test_chord_for_bar_wraps_the_progression():
    cue = SectionCue(chords=["Am7", "Dm7", "G7"])

    assert [chord_for_bar(cue, i) for i in range(4)] == ["Am7", "Dm7", "G7", "Am7"]


def test_resolve_soloist_defers_to_tacet():
    cue = SectionCue(chords=["Am7"], soloist=Instrument.FLUTE, tacet=[Instrument.FLUTE])

    assert resolve_soloist(cue) is None


def test_resolve_soloist_keeps_a_playing_soloist():
    cue = SectionCue(chords=["Am7"], soloist=Instrument.VIOLIN, tacet=[Instrument.DRUMS])

    assert resolve_soloist(cue) is Instrument.VIOLIN


def test_render_history_is_compact_and_skips_silent_parts():
    bar = Bar(
        index=1,
        chord="Am7",
        parts={
            Instrument.KEYS: BarPart(
                instrument=Instrument.KEYS, bar=1, notes=[Note(pitch=69, start=0.0, dur=0.5)]
            ),
            Instrument.FLUTE: BarPart(instrument=Instrument.FLUTE, bar=1, notes=[]),
        },
    )

    rendered = _render_history([bar], 16)

    assert "keys: 69@0/8" in rendered
    assert "flute" not in rendered


def test_render_history_handles_first_bar():
    assert "none" in _render_history([], 16)


def test_render_history_counts_in_the_bars_own_steps():
    bar = Bar(
        index=0,
        parts={
            Instrument.KEYS: BarPart(
                instrument=Instrument.KEYS, bar=0, notes=[Note(pitch=60, start=0.5, dur=2 / 14)]
            )
        },
    )

    rendered = _render_history([bar], 14)

    assert "keys: 60@7/2" in rendered


async def test_player_returns_notes(player_payload):
    provider = FakeProvider({"PlayerOutput": player_payload})
    agent = InstrumentAgent(Instrument.KEYS, provider)

    part = await agent.play(
        bar_index=0, cue=SectionCue(chords=["Am7"]), history=[], chord="Am7"
    )

    assert [n.pitch for n in part.notes] == [60, 64]
    assert part.instrument is Instrument.KEYS


async def test_player_stays_silent_when_tacet(player_payload):
    provider = FakeProvider({"PlayerOutput": player_payload})
    agent = InstrumentAgent(Instrument.DRUMS, provider)

    part = await agent.play(
        bar_index=0,
        cue=SectionCue(chords=["Am7"], tacet=[Instrument.DRUMS]),
        history=[],
        chord="Am7",
    )

    assert part.notes == []
    assert provider.calls == []


async def test_player_degrades_to_silence_on_generation_failure(player_payload):
    provider = FakeProvider({"PlayerOutput": player_payload})
    provider.fail_for = {"PlayerOutput"}
    agent = InstrumentAgent(Instrument.VIOLIN, provider)

    part = await agent.play(
        bar_index=3, cue=SectionCue(chords=["Am7"]), history=[], chord="Am7"
    )

    assert part.notes == []
    assert part.bar == 3


async def test_player_prompt_mentions_the_solo():
    provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})
    agent = InstrumentAgent(Instrument.FLUTE, provider)

    await agent.play(
        bar_index=0,
        cue=SectionCue(chords=["Am7"], soloist=Instrument.FLUTE),
        history=[],
        chord="Am7",
    )

    assert "You have the solo" in provider.calls[0]["user"]


@pytest.mark.parametrize(
    ("signature", "expected"),
    [
        ("4/4", "4/4 at 96 bpm — 16 steps per bar, 4 steps per quarter-note beat."),
        ("6/8", "6/8 at 96 bpm — 12 steps per bar, 4 steps per quarter-note beat."),
        ("7/8", "7/8 at 96 bpm — 14 steps per bar, 4 steps per quarter-note beat; counted 3+2+2"),
    ],
)
async def test_player_prompt_carries_key_and_meter(signature, expected):
    provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

    await InstrumentAgent(Instrument.KEYS, provider).play(
        bar_index=0,
        cue=SectionCue(chords=["Am7"]),
        history=[],
        chord="Am7",
        feel=Feel(key="E minor", tempo=96, time_signature=signature),
    )

    prompt = provider.calls[0]["user"]
    assert "Key: E minor." in prompt
    assert expected in prompt


async def test_player_prompt_names_the_next_chord():
    provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

    await InstrumentAgent(Instrument.KEYS, provider).play(
        bar_index=1, cue=SectionCue(chords=["Am7", "Dm7", "G7"]), history=[], chord="Dm7"
    )

    assert "Chord this bar: Dm7; next bar: G7." in provider.calls[0]["user"]


async def test_player_prompt_does_not_guess_past_the_section():
    provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

    await InstrumentAgent(Instrument.KEYS, provider).play(
        bar_index=3,
        cue=SectionCue(chords=["Am7", "Dm7"]),
        history=[],
        chord="Dm7",
        position=(3, 4),
    )

    prompt = provider.calls[0]["user"]
    assert "Bar 4 of 4 in this section." in prompt
    assert "next bar: (new section)." in prompt


async def test_player_steps_convert_on_the_bars_own_grid():
    provider = FakeProvider(
        {"PlayerOutput": {"notes": [{"pitch": 60, "step": 7, "len": 2, "vel": 90}]}}
    )

    part = await InstrumentAgent(Instrument.KEYS, provider).play(
        bar_index=0,
        cue=SectionCue(chords=["Am7"]),
        history=[],
        chord="Am7",
        feel=Feel(time_signature="7/8"),
    )

    assert part.notes[0].start == 0.5
    assert part.notes[0].dur == 2 / 14


async def test_player_step_past_the_bar_is_discarded():
    provider = FakeProvider(
        {
            "PlayerOutput": {
                "notes": [
                    {"pitch": 60, "step": 14, "len": 1},
                    {"pitch": 62, "step": 13, "len": 99},
                ]
            }
        }
    )

    part = await InstrumentAgent(Instrument.KEYS, provider).play(
        bar_index=0,
        cue=SectionCue(chords=["Am7"]),
        history=[],
        chord="Am7",
        feel=Feel(time_signature="7/8"),
    )

    assert [n.pitch for n in part.notes] == [62]
    assert part.notes[0].dur == 4.0


async def test_player_still_accepts_legacy_fractional_notes():
    provider = FakeProvider(
        {"PlayerOutput": {"notes": [{"pitch": 60, "start": 0.333, "dur": 0.25}]}}
    )

    part = await InstrumentAgent(Instrument.KEYS, provider).play(
        bar_index=0,
        cue=SectionCue(chords=["Am7"]),
        history=[],
        chord="Am7",
        feel=Feel(time_signature="3/4"),
    )

    assert (part.notes[0].start, part.notes[0].dur) == (0.333, 0.25)


async def test_bandleader_falls_back_to_previous_cue_on_failure(cue_payload):
    provider = FakeProvider({"SectionCue": cue_payload})
    provider.fail_for = {"SectionCue"}
    leader = Bandleader(provider)
    previous = SectionCue(chords=["Fmaj7"], section="chorus")

    cue = await leader.next_cue(bar_index=8, key="A minor", previous=previous, steer={})

    assert cue.section == "chorus"


async def test_bandleader_prompt_carries_tempo_and_meter(cue_payload):
    provider = FakeProvider({"SectionCue": cue_payload})

    await Bandleader(provider).next_cue(
        bar_index=0, key="E minor", previous=None, steer={}, tempo=132, time_signature="7/8"
    )

    assert "E minor, 7/8 at 132 bpm" in provider.calls[0]["user"]


async def test_bandleader_has_a_default_when_there_is_no_previous_cue(cue_payload):
    provider = FakeProvider({"SectionCue": cue_payload})
    provider.fail_for = {"SectionCue"}

    cue = await Bandleader(provider).next_cue(bar_index=0, key="A minor", previous=None, steer={})

    assert len(cue.chords) == 4


async def test_orchestrator_plays_all_five_instruments_per_bar(player_payload):
    provider = FakeProvider({"PlayerOutput": player_payload})
    orchestrator = BandOrchestrator(provider)

    bar = await orchestrator.play_bar(bar_index=0, cue=SectionCue(chords=["Am7"]), history=[])

    assert set(bar.parts) == set(BAND)
    assert bar.chord == "Am7"


async def test_orchestrator_composes_a_song_from_the_plan(song_plan_payload, player_payload):
    provider = FakeProvider({"SongPlan": song_plan_payload, "PlayerOutput": player_payload})
    orchestrator = BandOrchestrator(provider)

    song = await orchestrator.compose("something rainy")

    assert song.title == "Monsoon Line"
    assert song.tempo == 92
    assert len(song.bars) == 2
    assert [bar.chord for bar in song.bars] == ["Am7", "Dm7"]


async def test_orchestrator_tells_players_the_key_tempo_and_place(
    song_plan_payload, player_payload
):
    provider = FakeProvider({"SongPlan": song_plan_payload, "PlayerOutput": player_payload})

    await BandOrchestrator(provider).compose("something rainy")

    prompts = [call["user"] for call in provider.calls if call["schema"] == "PlayerOutput"]
    assert f"Key: {song_plan_payload['key']}." in prompts[0]
    assert "at 92 bpm" in prompts[0]
    assert "next bar: (new section)." in prompts[-1]


async def test_orchestrator_hoists_agent_patches_onto_the_song(song_plan_payload, player_payload):
    patched = {
        **player_payload,
        "patch": {
            "oscillator": "fmsine",
            "attack": 0.1,
            "decay": 0.2,
            "sustain": 0.7,
            "release": 0.5,
        },
    }
    provider = FakeProvider({"SongPlan": song_plan_payload, "PlayerOutput": patched})

    song = await BandOrchestrator(provider).compose("dreamy")

    assert song.patches[Instrument.VIOLIN].oscillator == "fmsine"


async def test_orchestrator_limits_history_context(player_payload):
    provider = FakeProvider({"PlayerOutput": player_payload})
    orchestrator = BandOrchestrator(provider)
    history = [Bar(index=i, chord="Am7", parts={}) for i in range(6)]

    await orchestrator.play_bar(bar_index=6, cue=SectionCue(chords=["Am7"]), history=history)

    prompt = provider.calls[0]["user"]
    assert "bar 4" in prompt and "bar 5" in prompt
    assert "bar 0" not in prompt


async def test_orchestrator_limits_concurrent_model_calls():
    """A tight tokens-per-minute budget cannot absorb five reasoning calls at once."""
    import asyncio

    peak = 0
    active = 0

    class Counting(FakeProvider):
        async def structured(self, **kwargs):
            nonlocal peak, active
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return await super().structured(**kwargs)

    provider = Counting({"PlayerOutput": {"notes": [], "patch": None}})
    orchestrator = BandOrchestrator(provider, max_concurrency=2)

    await orchestrator.play_bar(bar_index=0, cue=SectionCue(chords=["Am7"]), history=[])

    assert peak <= 2


async def test_orchestrator_defaults_to_playing_the_whole_band_at_once(player_payload):
    provider = FakeProvider({"PlayerOutput": player_payload})

    orchestrator = BandOrchestrator(provider, max_concurrency=5)

    assert orchestrator._gate._value == 5


class TestHarmonyBriefing:
    """The theory module exists so prompts carry notes, not just a symbol."""

    async def test_a_player_is_told_the_actual_notes(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})
        agent = InstrumentAgent(Instrument.VIOLIN, provider)

        await agent.play(
            bar_index=0, cue=SectionCue(chords=["Am9"]), history=[], chord="Am9"
        )

        prompt = provider.calls[0]["user"]
        assert "A C E G B" in prompt
        assert "Avoid landing on" in prompt

    async def test_the_soloist_is_given_a_wider_register(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

        await InstrumentAgent(Instrument.FLUTE, provider).play(
            bar_index=0,
            cue=SectionCue(chords=["Am9"], soloist=Instrument.FLUTE),
            history=[],
            chord="Am9",
        )
        solo_prompt = provider.calls[0]["user"]

        provider.calls.clear()
        await InstrumentAgent(Instrument.FLUTE, provider).play(
            bar_index=0,
            cue=SectionCue(chords=["Am9"], soloist=Instrument.VIOLIN),
            history=[],
            chord="Am9",
        )
        support_prompt = provider.calls[0]["user"]

        assert solo_prompt != support_prompt
        assert "register" in solo_prompt.lower()

    async def test_the_drummer_gets_no_harmony_lecture(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

        await InstrumentAgent(Instrument.DRUMS, provider).play(
            bar_index=0, cue=SectionCue(chords=["Am9"]), history=[], chord="Am9"
        )

        assert "Chord tones" not in provider.calls[0]["user"]

    async def test_an_unparseable_chord_does_not_break_the_prompt(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

        part = await InstrumentAgent(Instrument.KEYS, provider).play(
            bar_index=0, cue=SectionCue(chords=["N.C."]), history=[], chord="N.C."
        )

        assert part.notes == []
        assert "no fixed harmony" in provider.calls[0]["user"]


class TestFailureIsMusical:
    """A player that loses a bar should cover, not vanish.

    Provider failures are routine on a rate-limited tier. Returning silence
    for the keys removes the harmonic floor mid-piece, which is worse than
    anything the player might have written.
    """

    async def test_a_sustaining_player_holds_its_previous_notes(self, player_payload):
        provider = FakeProvider({"PlayerOutput": player_payload})
        provider.fail_for = {"PlayerOutput"}
        agent = InstrumentAgent(Instrument.KEYS, provider)
        previous = Bar(index=4, chord="Am7", parts={
            Instrument.KEYS: BarPart(
                instrument=Instrument.KEYS,
                bar=4,
                notes=[Note(pitch=57, start=0.0, dur=0.9, vel=60)],
            )
        })

        part = await agent.play(
            bar_index=5, cue=SectionCue(chords=["Am7"]), history=[previous], chord="Am7"
        )

        assert [n.pitch for n in part.notes] == [57]
        assert part.bar == 5

    async def test_the_held_bar_is_quieter_than_what_it_repeats(self, player_payload):
        provider = FakeProvider({"PlayerOutput": player_payload})
        provider.fail_for = {"PlayerOutput"}
        previous = Bar(index=0, chord="Am7", parts={
            Instrument.VIOLIN: BarPart(
                instrument=Instrument.VIOLIN,
                bar=0,
                notes=[Note(pitch=69, start=0.0, dur=0.5, vel=100)],
            )
        })

        part = await InstrumentAgent(Instrument.VIOLIN, provider).play(
            bar_index=1, cue=SectionCue(chords=["Am7"]), history=[previous], chord="Am7"
        )

        assert part.notes[0].vel < 100

    async def test_drums_keep_time_rather_than_repeat_a_fill(self, player_payload):
        """Repeating a drum bar re-triggers its fill; a plain pulse is safer."""
        provider = FakeProvider({"PlayerOutput": player_payload})
        provider.fail_for = {"PlayerOutput"}
        previous = Bar(index=0, chord="Am7", parts={
            Instrument.DRUMS: BarPart(
                instrument=Instrument.DRUMS,
                bar=0,
                notes=[Note(piece="tom_hi", start=i * 0.1, dur=0.08) for i in range(8)],
            )
        })

        part = await InstrumentAgent(Instrument.DRUMS, provider).play(
            bar_index=1, cue=SectionCue(chords=["Am7"]), history=[previous], chord="Am7"
        )

        assert {n.piece for n in part.notes} <= {"kick", "hat_closed", "snare"}

    async def test_a_player_with_no_history_stays_silent(self, player_payload):
        """Nothing to hold: silence is the only honest option."""
        provider = FakeProvider({"PlayerOutput": player_payload})
        provider.fail_for = {"PlayerOutput"}

        part = await InstrumentAgent(Instrument.FLUTE, provider).play(
            bar_index=0, cue=SectionCue(chords=["Am7"]), history=[], chord="Am7"
        )

        assert part.notes == []

    async def test_a_tacet_player_is_not_resurrected_by_a_failure(self, player_payload):
        """Silence the bandleader asked for must survive a provider failure."""
        provider = FakeProvider({"PlayerOutput": player_payload})
        provider.fail_for = {"PlayerOutput"}
        previous = Bar(index=0, chord="Am7", parts={
            Instrument.GUITAR: BarPart(
                instrument=Instrument.GUITAR,
                bar=0,
                notes=[Note(pitch=52, start=0.0, dur=0.5, vel=80)],
            )
        })

        part = await InstrumentAgent(Instrument.GUITAR, provider).play(
            bar_index=1,
            cue=SectionCue(chords=["Am7"], tacet=[Instrument.GUITAR]),
            history=[previous],
            chord="Am7",
        )

        assert part.notes == []


_BRIEF = {
    "groove": {"kick": [0, 6, 10], "snare": [6], "hat": [0, 2, 4, 6, 8, 10, 12]},
    "comp_rhythm": [0, 6, 10],
    "motif": [{"step": 0, "len": 4, "degree": 1}, {"step": 6, "len": 2, "degree": 5}],
    "motif_development": "sequence up a step",
    "roles": {"violin": {"register": "high"}},
    "energy_curve": [4, 6],
    "call_response": [{"bar": 0, "lead": "violin"}],
}


class TestScoreFirstArrangement:
    """The rhythm section plays to a shared brief; the melody hears it play."""

    def test_a_garbled_brief_degrades_item_by_item(self):
        cue = SectionCue(
            chords=["Am7"],
            brief={
                "groove": {"kick": [0, "x", 99, 8], "cowbell": [1]},
                "motif": [{"step": 0, "degree": 3}, {"degree": 12}, "nonsense"],
                "roles": {"tuba": {"register": "low"}, "keys": {"register": "sky"}},
                "energy_curve": [3, 42, "loud"],
                "call_response": [{"bar": 1, "lead": "kazoo"}],
            },
        )

        assert cue.brief.groove == {"kick": [0, 8]}
        assert [n.degree for n in cue.brief.motif] == [3]
        assert cue.brief.roles == {}
        assert cue.brief.energy_curve == [3, 10]
        assert cue.brief.call_response == []

    def test_a_brief_that_is_not_an_object_is_dropped(self):
        assert SectionCue(chords=["Am7"], brief="play nice").brief is None

    async def test_layer_a_is_told_the_groove(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

        await BandOrchestrator(provider).play_bar(
            bar_index=0, cue=SectionCue(chords=["Am7"], brief=_BRIEF), history=[]
        )

        drums = provider.calls[0]["user"]
        assert "kick [0, 6, 10]" in drums
        assert "Comp rhythm (stab on steps): [0, 6, 10]" in provider.calls[2]["user"]

    async def test_layer_b_hears_layer_a_s_current_bar(self, player_payload):
        provider = FakeProvider({"PlayerOutput": player_payload})

        await BandOrchestrator(provider).play_bar(
            bar_index=0,
            cue=SectionCue(chords=["Am7"], brief=_BRIEF),
            history=[],
            feel=Feel(key="A minor", tempo=120, time_signature="7/8"),
            position=(0, 2),
        )

        rhythm, melody = provider.calls[:4], provider.calls[4:]
        assert all("Right now the others play" not in c["user"] for c in rhythm)
        violin = melody[1]["user"]
        assert "Right now the others play" in violin
        assert "  keys: 60@0/" in violin
        assert "Motif (scale degree@step/len): 1@0/4 5@6/2" in violin
        assert "You lead this bar." in violin

    async def test_bass_is_in_the_rhythm_layer_and_reads_the_bass_rhythm(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})

        await BandOrchestrator(provider).play_bar(
            bar_index=0,
            cue=SectionCue(chords=["Am7"], brief={**_BRIEF, "bass_rhythm": [0, 6, 10]}),
            history=[],
        )

        bass = provider.calls[1]
        assert bass["system"].startswith("You are the bassist")
        assert "Bass rhythm (play on steps): [0, 6, 10]" in bass["user"]
        assert "Right now the others play" not in bass["user"]

    async def test_compose_stream_yields_the_plan_then_bars_in_order(
        self, song_plan_payload, player_payload
    ):
        from app.agents.bandleader import SongPlan

        provider = FakeProvider({"SongPlan": song_plan_payload, "PlayerOutput": player_payload})
        orchestrator = BandOrchestrator(provider)

        items = [item async for item in orchestrator.compose_stream("rain")]
        song = await orchestrator.compose("rain")

        assert isinstance(items[0], SongPlan)
        assert [bar.index for bar in items[1:]] == [0, 1]
        assert song.bars == items[1:]

    async def test_a_cover_fades_to_silence_after_two_bars(self):
        provider = FakeProvider({"PlayerOutput": {"notes": [], "patch": None}})
        provider.fail_for = {"PlayerOutput"}
        agent = InstrumentAgent(Instrument.KEYS, provider)
        previous = Bar(index=0, chord="Am7", parts={
            Instrument.KEYS: BarPart(
                instrument=Instrument.KEYS, bar=0, notes=[Note(pitch=57, start=0.0, dur=0.9)]
            )
        })
        cue = SectionCue(chords=["Am7"])

        covered = [
            await agent.play(bar_index=i, cue=cue, history=[previous], chord="Am7")
            for i in (1, 2, 3)
        ]

        assert [len(part.notes) for part in covered] == [1, 1, 0]

    async def test_temperature_follows_the_role(self, player_payload):
        provider = FakeProvider({"PlayerOutput": player_payload})

        await BandOrchestrator(provider).play_bar(
            bar_index=0, cue=SectionCue(chords=["Am7"]), history=[]
        )

        temperatures = {
            c["system"].split(".")[0]: c["temperature"] for c in provider.calls
        }
        assert sorted(temperatures.values()) == [0.5, 0.5, 0.7, 0.7, 0.8, 0.8]
        assert temperatures["You are the drummer"] == 0.5
        assert temperatures["You are the bassist"] == 0.5
