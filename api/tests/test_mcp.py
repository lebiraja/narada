"""The MCP surface: what an external agent can actually do to the band."""

import json

import pytest

from app.agents.orchestrator import BandOrchestrator
from app.core.schema import Instrument
from app.core.session import JamSession
from app.mcp import server
from tests.conftest import FakeProvider, FakeStore


@pytest.fixture(autouse=True)
def wired(store: FakeStore, player_payload):
    """Every MCP test runs against an in-memory store and a fake band."""
    server.configure(store, BandOrchestrator(FakeProvider({"PlayerOutput": player_payload})))
    yield store
    server.configure(None, None)


def _notes(*pitches: int) -> list[dict]:
    return [{"pitch": p, "start": i * 0.25, "dur": 0.25, "vel": 90} for i, p in enumerate(pitches)]


async def test_band_state_starts_empty(wired):
    state = json.loads(await server.band_state())

    assert state["next_bar"] == 0
    assert state["tempo"] == 96
    assert state["recent_bars"] == []


async def test_set_tempo_and_key(wired):
    result = await server.band_set_tempo(120, key="D dorian")

    assert "120" in result and "D dorian" in result
    state = json.loads(await server.band_state())
    assert state["tempo"] == 120
    assert state["key"] == "D dorian"


async def test_set_tempo_clamps_out_of_range_values(wired):
    await server.band_set_tempo(9000)

    assert json.loads(await server.band_state())["tempo"] == 240


async def test_play_bar_writes_notes_and_advances(wired):
    result = await server.play_bar("violin", _notes(67, 69))

    assert "violin bar 0: 2 notes" in result
    state = json.loads(await server.band_state())
    assert state["next_bar"] == 1
    assert len(state["recent_bars"][0]["parts"]["violin"]["notes"]) == 2


async def test_play_bar_layers_instruments_into_one_bar(wired):
    await server.play_bar("drums", _notes(36, 38), bar=0)
    await server.play_bar("keys", _notes(60), bar=0)

    bars = json.loads(await server.band_state())["recent_bars"]

    assert len(bars) == 1
    assert set(bars[0]["parts"]) == {"drums", "keys"}


async def test_play_bar_reports_dropped_out_of_range_notes(wired):
    result = await server.play_bar("flute", _notes(72, 20))

    assert "1 notes" in result
    assert "1 out-of-range notes dropped" in result


async def test_play_bar_rejects_an_unknown_instrument(wired):
    result = await server.play_bar("kazoo", _notes(60))

    assert result.startswith("rejected:")
    assert json.loads(await server.band_state())["next_bar"] == 0


async def test_play_bar_rejects_malformed_notes(wired):
    result = await server.play_bar("keys", [{"pitch": 60, "start": 5.0, "dur": 0.25}])

    assert result.startswith("rejected:")


async def test_set_patch_stores_a_valid_voice(wired):
    patch = {
        "oscillator": "fmsine",
        "attack": 0.1,
        "decay": 0.2,
        "sustain": 0.7,
        "release": 0.5,
        "filter_freq": 6000,
        "filter_q": 2,
        "reverb": 0.4,
        "delay": 0,
    }

    result = await server.set_patch("violin", patch)

    assert "fmsine" in result
    session = await wired.load(server.MCP_SESSION)
    assert session.steer["patches"]["violin"]["oscillator"] == "fmsine"


async def test_set_patch_rejects_an_invalid_oscillator(wired):
    result = await server.set_patch("flute", {"oscillator": "bagpipe", "attack": 0.1,
                                              "decay": 0.1, "sustain": 0.5, "release": 0.2})

    assert result.startswith("rejected:")


async def test_band_play_generates_bars_through_the_agents(wired):
    result = await server.band_play("swing it, keep it sparse", bars=3)

    assert "3 bars" in result
    state = json.loads(await server.band_state())
    assert state["next_bar"] == 3
    assert set(state["recent_bars"][0]["parts"]) == {i.value for i in Instrument}


async def test_band_play_clamps_the_bar_count(wired):
    await server.band_play("go", bars=99)

    assert json.loads(await server.band_state())["next_bar"] == 16


async def test_band_play_uses_the_chords_it_is_given(wired):
    await server.band_play("modal", bars=2, chords=["Dm7", "Em7"])

    bars = json.loads(await server.band_state())["recent_bars"]

    assert [bar["chord"] for bar in bars] == ["Dm7", "Em7"]


async def test_band_reset_clears_everything(wired):
    await server.play_bar("keys", _notes(60))

    await server.band_reset()

    assert json.loads(await server.band_state())["next_bar"] == 0


async def test_manual_and_generated_bars_share_a_timeline(wired):
    """An agent writing a bar by hand and the band generating should interleave."""
    await server.play_bar("flute", _notes(72))
    await server.band_play("answer that phrase", bars=1)

    state = json.loads(await server.band_state())

    assert state["next_bar"] == 2
    assert list(state["recent_bars"][0]["parts"]) == ["flute"]
    assert len(state["recent_bars"][1]["parts"]) == 5


async def test_play_bar_records_the_chord(wired):
    await server.play_bar("violin", _notes(69), bar=0, chord="Am9")

    assert json.loads(await server.band_state())["recent_bars"][0]["chord"] == "Am9"


async def test_a_later_write_can_name_the_chord_of_an_existing_bar(wired):
    await server.play_bar("violin", _notes(69), bar=0)
    await server.play_bar("keys", _notes(57), bar=0, chord="Dm7")

    bar = json.loads(await server.band_state())["recent_bars"][0]

    assert bar["chord"] == "Dm7"
    assert sorted(bar["parts"]) == ["keys", "violin"]


async def test_writing_an_earlier_bar_does_not_rewind_the_playhead(wired):
    await server.play_bar("violin", _notes(69))   # bar 0
    await server.play_bar("keys", _notes(57))     # bar 1
    await server.play_bar("flute", _notes(72), bar=0)

    assert json.loads(await server.band_state())["next_bar"] == 2


async def test_instrument_names_are_accepted_as_a_musician_writes_them(wired):
    result = await server.play_bar("Violin", _notes(69))

    assert result.startswith("violin bar 0")


async def test_rejecting_an_unknown_instrument_names_the_band(wired):
    result = await server.play_bar("trombone", _notes(60))

    assert "trombone" in result
    assert "drums, keys, guitar, flute, violin" in result


async def test_rejecting_a_bad_note_explains_the_units(wired):
    result = await server.play_bar("keys", [{"pitch": 60, "start": 5.0, "dur": 0.25}])

    assert "start" in result
    assert "fraction of the bar" in result
    assert "https://" not in result  # no raw pydantic URLs


async def test_rejecting_a_bad_patch_is_readable(wired):
    result = await server.set_patch("flute", {"oscillator": "bagpipe", "attack": 0.1,
                                              "decay": 0.1, "sustain": 0.5, "release": 0.2})

    assert "oscillator" in result
    assert "https://" not in result


async def test_every_tool_is_registered_with_mcp():
    tools = {tool.name for tool in await server.mcp.list_tools()}

    assert tools == {
        "band_state",
        "band_set_tempo",
        "play_bar",
        "set_patch",
        "band_play",
        "band_reset",
    }


async def test_tools_expose_descriptions_for_the_calling_agent():
    for tool in await server.mcp.list_tools():
        assert tool.description, f"{tool.name} has no description"
