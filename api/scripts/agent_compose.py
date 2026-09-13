"""Compose a piece with the real agents and report what actually happened.

    docker compose exec -T -e PYTHONPATH=/app api python scripts/agent_compose.py \
        "brief" [max_bars] > song.json
"""

import asyncio
import sys
import time

from app.agents.orchestrator import BandOrchestrator
from app.core.provider import GenerationError
from app.core.schema import BAND, Song


async def main() -> None:
    brief = sys.argv[1] if len(sys.argv) > 1 else "something restless in 6/8"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 16

    band = BandOrchestrator()
    started = time.monotonic()

    try:
        plan = await band.leader.plan_song(brief)
    except GenerationError as exc:
        print(f"bandleader failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"{plan.title} — {plan.key}, {plan.time_signature}, {plan.tempo}bpm", file=sys.stderr)
    for section in plan.sections:
        print(f"  {section.section:10} {section.bars:>2} bars  {' '.join(section.chords)}"
              f"  solo={section.soloist or '-'}  tacet={[t.value for t in section.tacet] or '-'}",
              file=sys.stderr)

    song = Song(title=plan.title, key=plan.key, tempo=plan.tempo,
                time_signature=plan.time_signature)

    index = 0
    for section in plan.sections:
        if index >= cap:
            break
        cue = section.model_copy()
        for offset in range(section.bars):
            if index >= cap:
                break
            bar = await band.play_bar(bar_index=index, cue=cue, history=song.bars)
            counts = {i.value: len(bar.parts[i].notes) for i in BAND if i in bar.parts}
            silent = [k for k, v in counts.items() if v == 0]
            print(f"  bar {index:>2} [{bar.chord:<6}] "
                  f"{sum(counts.values()):>3} notes  silent={silent or '-'}", file=sys.stderr)
            for instrument, part in bar.parts.items():
                if part.patch:
                    song.patches[instrument] = part.patch
            song.bars.append(bar)
            index += 1

    elapsed = time.monotonic() - started
    total = sum(len(p.notes) for b in song.bars for p in b.parts.values())
    empty = sum(1 for b in song.bars for p in b.parts.values() if not p.notes)
    print(f"\n{len(song.bars)} bars, {total} notes, {empty} silent parts, {elapsed:.0f}s",
          file=sys.stderr)
    print(song.model_dump_json())


if __name__ == "__main__":
    asyncio.run(main())
