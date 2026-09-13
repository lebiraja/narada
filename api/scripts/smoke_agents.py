"""One real call per agent role, to see what the configured model actually returns."""

import asyncio
import json

from app.agents.bandleader import Bandleader
from app.agents.instrument import InstrumentAgent
from app.core.provider import GenerationError, LLMProvider
from app.core.schema import Instrument, SectionCue


async def main() -> None:
    provider = LLMProvider()

    print("— bandleader planning a song —")
    try:
        plan = await Bandleader(provider).plan_song("a restless monsoon evening in 6/8")
        print(f"  {plan.title} | {plan.key} | {plan.tempo}bpm | {plan.total_bars} bars")
        for section in plan.sections:
            print(f"    {section.section:10} {section.bars:>2} bars  {section.chords}"
                  f"  solo={section.soloist}")
    except GenerationError as exc:
        print(f"  FAILED: {exc}")
        return

    print("\n— each player writing bar 0 —")
    cue = SectionCue(chords=["Am9", "Dm7"], energy=6, density=5,
                     soloist=Instrument.VIOLIN, direction="loose, let it breathe")
    for instrument in Instrument:
        part = await InstrumentAgent(instrument, provider).play(
            bar_index=0, cue=cue, history=[], chord="Am9"
        )
        pitches = [f"{n.pitch}@{n.start:.2f}" for n in part.notes]
        print(f"  {instrument.value:8} {len(part.notes):>2} notes  {pitches[:6]}")


if __name__ == "__main__":
    asyncio.run(main())
