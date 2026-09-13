from app.core.schema import Bar, Instrument, SectionCue
from app.core.session import CUE_EVERY_BARS, JamSession, apply_steer
from app.ws.jam import _steered


def test_history_keeps_only_recent_bars():
    session = JamSession(id="s1")

    for i in range(10):
        session.remember(Bar(index=i, chord="Am7", parts={}))

    assert [bar.index for bar in session.history] == [6, 7, 8, 9]


def test_needs_new_cue_on_the_window_boundary():
    session = JamSession(id="s1")

    assert session.needs_new_cue() is True

    session.cue = SectionCue(chords=["Am7"])
    session.next_bar = 1
    assert session.needs_new_cue() is False

    session.next_bar = CUE_EVERY_BARS
    assert session.needs_new_cue() is True


def test_apply_steer_clamps_energy_and_tempo():
    session = JamSession(id="s1")

    apply_steer(session, {"energy": 99, "tempo": 1000})

    assert session.steer["energy"] == 10
    assert session.tempo == 240


def test_apply_steer_records_solo_and_drop():
    session = JamSession(id="s1")

    apply_steer(session, {"solo": "flute", "drop": ["drums"]})

    assert session.steer["solo"] == "flute"
    assert session.steer["drop"] == ["drums"]


def test_apply_steer_clears_solo():
    session = JamSession(id="s1", steer={"solo": "flute"})

    apply_steer(session, {"solo": None})

    assert session.steer["solo"] is None


def test_steered_overrides_the_bandleader_cue():
    cue = SectionCue(chords=["Am7"], energy=3, tacet=[Instrument.VIOLIN])

    result = _steered(cue, {"energy": 9, "solo": "flute", "drop": ["drums"]})

    assert result.energy == 9
    assert result.soloist is Instrument.FLUTE
    assert set(result.tacet) == {Instrument.VIOLIN, Instrument.DRUMS}


def test_steered_leaves_the_cue_alone_when_nothing_is_requested():
    cue = SectionCue(chords=["Fmaj7"], energy=4)

    assert _steered(cue, {}) is cue


def test_steered_has_a_default_cue_before_the_leader_speaks():
    assert _steered(None, {}).chords == ["Am7", "Dm7", "G7", "Cmaj7"]
