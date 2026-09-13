"""End-to-end check against the real app with a stubbed model.

Proves the wiring the unit tests mock out: routers, orchestrator, MIDI
rendering and the jam socket, all in one pass. Run inside the api container:

    docker compose exec -T api python scripts/wire_check.py
"""

import io
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.provider import LLMProvider
from app.main import app

PLAN = {
    "title": "Wire Check",
    "key": "A minor",
    "tempo": 92,
    "time_signature": "4/4",
    "sections": [
        {
            "section": "verse",
            "chords": ["Am7", "Dm7"],
            "energy": 6,
            "density": 5,
            "soloist": "flute",
            "tacet": [],
            "direction": "loose",
            "bars": 2,
        }
    ],
}
NOTES = {
    "notes": [
        {"pitch": 69, "start": 0.0, "dur": 0.25, "vel": 100},
        {"pitch": 72, "start": 0.5, "dur": 0.25, "vel": 88},
    ],
    "patch": None,
}


CUE = {
    "section": "verse",
    "chords": ["Am7", "Dm7"],
    "energy": 6,
    "density": 5,
    "soloist": "flute",
    "tacet": [],
    "direction": "loose",
}

PAYLOADS = {"SongPlan": PLAN, "SectionCue": CUE, "PlayerOutput": NOTES}


async def fake_structured(self, *, system, user, schema, **kwargs):
    return schema.model_validate(PAYLOADS[schema.__name__])


def main() -> None:
    with patch.object(LLMProvider, "structured", fake_structured):
        client = TestClient(app)

        response = client.post("/api/compose", json={"brief": "wire check"})
        assert response.status_code == 200, response.text
        song = response.json()
        print(f"compose      {len(song['bars'])} bars, "
              f"{len(song['bars'][0]['parts'])} players in bar 0")

        export = client.post("/api/export/midi", json=song)
        assert export.status_code == 200
        stems = zipfile.ZipFile(io.BytesIO(export.content)).namelist()
        print(f"export       {len(stems)} stems, {len(export.content)} bytes")

        with client.websocket_connect("/ws/jam") as socket:
            assert socket.receive_json()["type"] == "session"
            socket.send_json({"type": "steer", "energy": 9, "solo": "violin"})
            print(f"steer        {socket.receive_json()['steer']}")

            socket.send_json({"type": "need_bars", "from_bar": 0})
            stream = [socket.receive_json() for _ in range(3)]
            print(f"jam stream   {[m['type'] for m in stream]}")
            print(f"bar 0        {sorted(stream[1]['bar']['parts'])}")
            socket.send_json({"type": "stop"})

    print("\nwiring ok")


if __name__ == "__main__":
    main()
