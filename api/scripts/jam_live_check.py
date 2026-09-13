"""Drive the live jam socket with real agents and measure whether it keeps up.

The browser needs a bar roughly every (60/tempo)*beats seconds. If generation
is slower than that, the engine repeats the previous bar — audible, but not
silence. This reports the real margin.

    docker compose exec -T -e PYTHONPATH=/app api python scripts/jam_live_check.py
"""

import time

from fastapi.testclient import TestClient

from app.core.midi import beats_per_bar
from app.main import app

TEMPO = 96
SIGNATURE = "4/4"


def main() -> None:
    budget = (60 / TEMPO) * beats_per_bar(SIGNATURE)
    print(f"one bar lasts {budget:.1f}s at {TEMPO}bpm in {SIGNATURE}\n")

    client = TestClient(app)
    with client.websocket_connect("/ws/jam") as socket:
        hello = socket.receive_json()
        print(f"session {hello['id'][:8]} at {hello['tempo']}bpm")

        socket.send_json({"type": "steer", "energy": 7, "solo": "violin"})
        socket.receive_json()

        started = time.monotonic()
        socket.send_json({"type": "need_bars", "from_bar": 0})

        bars = 0
        previous = started
        while bars < 4:
            message = socket.receive_json()
            now = time.monotonic()
            if message["type"] == "cue":
                cue = message["cue"]
                print(f"  cue      {now - previous:5.1f}s  {cue['chords']} "
                      f"solo={cue['soloist']}")
            elif message["type"] == "bar":
                bar = message["bar"]
                counts = {k: len(v["notes"]) for k, v in bar["parts"].items() if v["notes"]}
                margin = budget - (now - previous)
                verdict = "ok" if margin > 0 else f"LATE by {-margin:.1f}s"
                print(f"  bar {bar['index']}    {now - previous:5.1f}s  "
                      f"{sum(counts.values()):>3} notes  {verdict}")
                bars += 1
            elif message["type"] == "error":
                print(f"  error    {message['detail'][:90]}")
                break
            previous = now

        total = time.monotonic() - started
        print(f"\n{bars} bars in {total:.0f}s — {total / max(bars, 1):.1f}s per bar "
              f"against a {budget:.1f}s budget")
        socket.send_json({"type": "stop"})


if __name__ == "__main__":
    main()
