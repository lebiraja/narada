import pytest

from app.agents.bandleader import Bandleader, chord_for_bar, resolve_soloist
from app.agents.instrument import InstrumentAgent, _render_history
from app.agents.orchestrator import BandOrchestrator
from app.core.schema import BAND, Bar, BarPart, Instrument, Note, SectionCue
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

    rendered = _render_history([bar])

    assert "keys: 69@0.00/0.50" in rendered
    assert "flute" not in rendered


def test_render_history_handles_first_bar():
    assert "none" in _render_history([])


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


async def test_bandleader_falls_back_to_previous_cue_on_failure(cue_payload):
    provider = FakeProvider({"SectionCue": cue_payload})
    provider.fail_for = {"SectionCue"}
    leader = Bandleader(provider)
    previous = SectionCue(chords=["Fmaj7"], section="chorus")

    cue = await leader.next_cue(bar_index=8, key="A minor", previous=previous, steer={})

    assert cue.section == "chorus"


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
