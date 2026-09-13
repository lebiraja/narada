"""What happens when the model misbehaves.

Every case here was found by running real agents against a real provider.
"""

import pytest
from openai import APIError, RateLimitError
from pydantic import ValidationError

from app.core.provider import MAX_RETRY_WAIT, GenerationError, LLMProvider, retry_after
from app.core.schema import (
    BarPart,
    Instrument,
    SectionCue,
    coerce_instruments,
    coerce_optional_instrument,
    salvage_notes,
)
from app.agents.instrument import PlayerOutput


class TestInstrumentAliases:
    """Models write 'Flute' and 'Piano'; the band still has to hear them."""

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("Flute", Instrument.FLUTE),
            ("FLUTE", Instrument.FLUTE),
            (" violin ", Instrument.VIOLIN),
            ("Piano", Instrument.KEYS),
            ("keyboard", Instrument.KEYS),
            ("Drum Kit", Instrument.DRUMS),
            ("percussion", Instrument.DRUMS),
            ("fiddle", Instrument.VIOLIN),
            ("Electric Guitar", Instrument.GUITAR),
        ],
    )
    def test_accepts_how_a_musician_would_write_it(self, written, expected):
        assert Instrument(written) is expected

    def test_still_rejects_an_instrument_not_in_the_band(self):
        with pytest.raises(ValueError):
            Instrument("Trombone")


class TestRosterCoercion:
    """A bandleader naming a trumpet describes a band we do not have."""

    def test_drops_instruments_outside_the_band(self):
        assert coerce_instruments(["Trumpet", "Flute", "Alto Sax", "drums"]) == [
            Instrument.FLUTE,
            Instrument.DRUMS,
        ]

    def test_deduplicates(self):
        assert coerce_instruments(["flute", "Flute"]) == [Instrument.FLUTE]

    def test_handles_a_non_list(self):
        assert coerce_instruments("flute") == []

    def test_optional_instrument_falls_back_to_nobody(self):
        assert coerce_optional_instrument("Alto Sax") is None
        assert coerce_optional_instrument(None) is None
        assert coerce_optional_instrument("Violin") is Instrument.VIOLIN

    def test_a_cue_survives_an_invented_horn_section(self):
        cue = SectionCue(
            chords=["Am"], soloist="Trumpet", tacet=["Trombone", "Flute", "Drums"]
        )

        assert cue.soloist is None
        assert cue.tacet == [Instrument.FLUTE, Instrument.DRUMS]


class TestNoteSalvage:
    """One misplaced note should cost that note, not the whole bar."""

    def test_drops_a_note_landing_on_the_next_downbeat(self):
        notes = salvage_notes(
            [
                {"pitch": 72, "start": 0.0, "dur": 0.25, "vel": 90},
                {"pitch": 74, "start": 1.0, "dur": 0.25, "vel": 90},
            ]
        )

        assert [n["pitch"] for n in notes] == [72]

    def test_clamps_values_where_the_intent_is_clear(self):
        [note] = salvage_notes([{"pitch": 60, "start": 0.5, "dur": 99, "vel": 300}])

        assert note["dur"] == 4.0
        assert note["vel"] == 127

    def test_drops_unusable_entries(self):
        assert salvage_notes([{"pitch": "high"}, "C4", None, {"start": 0.0}]) == []

    def test_player_output_keeps_the_good_notes(self):
        output = PlayerOutput.model_validate(
            {
                "notes": [
                    {"pitch": 72, "start": 0.0, "dur": 0.25, "vel": 90},
                    {"pitch": 74, "start": 1.0, "dur": 0.25, "vel": 90},
                    {"pitch": 76, "start": 0.5, "dur": 0.25, "vel": 90},
                ],
                "patch": None,
            }
        )

        assert [n.pitch for n in output.notes] == [72, 76]

    def test_player_output_discards_a_malformed_patch_but_keeps_notes(self):
        output = PlayerOutput.model_validate(
            {"notes": [{"pitch": 72, "start": 0.0, "dur": 0.25, "vel": 90}], "patch": "warm"}
        )

        assert output.patch is None
        assert len(output.notes) == 1

    def test_bar_part_still_enforces_instrument_range(self):
        part = BarPart.model_validate(
            {
                "instrument": "flute",
                "bar": 0,
                "notes": [
                    {"pitch": 72, "start": 0.0, "dur": 0.25, "vel": 90},
                    {"pitch": 20, "start": 0.5, "dur": 0.25, "vel": 90},
                ],
            }
        )

        assert [n.pitch for n in part.notes] == [72]


class TestRetryAfter:
    """Guessing shorter than the provider's own advice just burns a request."""

    def test_reads_the_wait_out_of_the_message(self):
        assert retry_after(Exception("Please try again in 9.6s.")) == pytest.approx(10.1)

    def test_falls_back_when_the_provider_says_nothing(self):
        assert retry_after(Exception("server exploded"), default=3.0) == 3.0

    def test_never_waits_longer_than_the_ceiling(self):
        assert retry_after(Exception("try again in 600s")) == MAX_RETRY_WAIT

    def test_prefers_the_retry_after_header(self):
        class Response:
            headers = {"retry-after": "4"}

        error = Exception("try again in 90s")
        error.response = Response()

        assert retry_after(error) == pytest.approx(4.5)


class FlakyClient:
    """Fails a set number of times, then returns valid JSON."""

    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.calls = 0
        self.error = error or ValueError("boom")
        self.chat = self

    @property
    def completions(self):
        return self

    async def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return _response('{"chords": ["Am7"], "energy": 4}')


def _response(content: str):
    class Message:
        pass

    message = Message()
    message.content = content
    choice = Message()
    choice.message = message
    result = Message()
    result.choices = [choice]
    return result


class TestProviderRetry:
    async def test_recovers_from_a_transient_failure(self, monkeypatch):
        client = FlakyClient(failures=1)
        monkeypatch.setattr("asyncio.sleep", _no_sleep)
        provider = LLMProvider(client=client)

        cue = await provider.structured(system="s", user="u", schema=SectionCue)

        assert cue.chords == ["Am7"]
        assert client.calls == 2

    async def test_gives_up_and_reports_a_generation_error(self, monkeypatch):
        client = FlakyClient(failures=5)
        monkeypatch.setattr("asyncio.sleep", _no_sleep)
        provider = LLMProvider(client=client)

        with pytest.raises(GenerationError):
            await provider.structured(system="s", user="u", schema=SectionCue)

        assert client.calls == 2  # default attempts

    async def test_an_empty_body_counts_as_a_failure(self, monkeypatch):
        class Empty(FlakyClient):
            async def create(self, **kwargs):
                self.calls += 1
                return _response("")

        client = Empty(failures=0)
        monkeypatch.setattr("asyncio.sleep", _no_sleep)

        with pytest.raises(GenerationError):
            await LLMProvider(client=client).structured(
                system="s", user="u", schema=SectionCue
            )


async def _no_sleep(_seconds):
    return None
