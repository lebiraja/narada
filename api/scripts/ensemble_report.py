"""Print ensemble metrics for the hand-written pieces: the baseline for "tight".

No LLM involved; the pieces are built by their compose scripts.

    docker compose run --rm --no-deps -e PYTHONPATH=/app api python scripts/ensemble_report.py
"""

import compose_monsoon
import compose_tandava

from app.core.metrics import ensemble_report


def _fmt(value: float | None) -> str:
    return "  -  " if value is None else f"{value:5.2f}"


if __name__ == "__main__":
    for song in (compose_monsoon.build(), compose_tandava.build()):
        report = ensemble_report(song)
        print(f"\n{song.title} ({song.time_signature}, {song.tempo}bpm, {len(song.bars)} bars)")
        for name, value in report.items():
            if isinstance(value, dict):
                cells = "  ".join(f"{k}={_fmt(v).strip()}" for k, v in value.items())
                print(f"  {name:32} {cells}")
            else:
                print(f"  {name:32} {_fmt(value)}")
