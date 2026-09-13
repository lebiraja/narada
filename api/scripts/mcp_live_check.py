"""Exercise the MCP tools against real infrastructure and a real model.

Unlike tests/test_mcp.py this uses the actual Redis-backed store and, for
band_play, the configured model — so it proves the tools work as an external
agent would find them.

    docker compose exec -T -e PYTHONPATH=/app api python scripts/mcp_live_check.py
"""

import asyncio
import json

from app.mcp import server


def show(label: str, result: str) -> None:
    print(f"  {label:<22} {result}")


async def main() -> None:
    await server.band_reset()

    print("— tool surface —")
    tools = await server.mcp.list_tools()
    for tool in sorted(tools, key=lambda t: t.name):
        required = tool.inputSchema.get("required", [])
        print(f"  {tool.name:<18} args={required}")

    print("\n— transport —")
    show("set tempo/key", await server.band_set_tempo(84, key="A dorian"))
    state = json.loads(await server.band_state())
    assert state["tempo"] == 84 and state["key"] == "A dorian"

    print("\n— writing bars by hand —")
    show("violin bar 0", await server.play_bar("violin", [
        {"pitch": 69, "start": 0.0, "dur": 0.33, "vel": 80},
        {"pitch": 76, "start": 0.33, "dur": 0.34, "vel": 88},
        {"pitch": 74, "start": 0.67, "dur": 0.33, "vel": 76},
    ], bar=0))
    show("keys layered on 0", await server.play_bar("keys", [
        {"pitch": 57, "start": 0.0, "dur": 0.95, "vel": 48},
        {"pitch": 64, "start": 0.0, "dur": 0.95, "vel": 44},
    ], bar=0))

    print("\n— validation —")
    show("unknown instrument", await server.play_bar("kazoo", [{"pitch": 60, "start": 0, "dur": 0.2}]))
    show("out-of-range pitch", await server.play_bar("flute", [
        {"pitch": 72, "start": 0.0, "dur": 0.25, "vel": 90},
        {"pitch": 20, "start": 0.5, "dur": 0.25, "vel": 90},
    ], bar=1))
    show("bad start", await server.play_bar("keys", [{"pitch": 60, "start": 5.0, "dur": 0.25}], bar=1))

    print("\n— patches —")
    show("valid patch", await server.set_patch("violin", {
        "oscillator": "fmsine", "attack": 0.12, "decay": 0.3, "sustain": 0.85,
        "release": 0.9, "filter_freq": 7000, "filter_q": 1.4, "reverb": 0.45, "delay": 0.0}))
    show("invalid oscillator", await server.set_patch("flute", {
        "oscillator": "bagpipe", "attack": 0.1, "decay": 0.1, "sustain": 0.5, "release": 0.2}))

    print("\n— handing it to the agents —")
    show("band_play", await server.band_play("answer that violin phrase, stay sparse", bars=2))

    state = json.loads(await server.band_state())
    print(f"\n— final state —\n  tempo={state['tempo']} key={state['key']} next_bar={state['next_bar']}")
    for bar in state["recent_bars"]:
        counts = {k: len(v["notes"]) for k, v in bar["parts"].items() if v["notes"]}
        print(f"  bar {bar['index']} [{bar['chord']}] {counts}")

    await server.band_reset()
    assert json.loads(await server.band_state())["next_bar"] == 0
    print("\nmcp pipeline ok")


if __name__ == "__main__":
    asyncio.run(main())
