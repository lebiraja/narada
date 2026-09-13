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
