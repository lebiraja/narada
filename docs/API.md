# API

Base URL: `http://localhost:8000`

## `GET /health`

```json
{"status": "ok"}
```

## `POST /api/compose`

Brief the bandleader; get back a complete arrangement. This runs the full band
(one leader call + five player calls per bar), so a 32-bar piece is 160+ model
calls and takes a while.

**Request**

```json
{"brief": "a rainy Chennai evening, slow 6/8, violin carries it"}
```

**Response** — a `Song`:

```json
{
  "title": "Monsoon Line",
  "key": "A minor",
  "tempo": 68,
  "time_signature": "4/4",
  "patches": {"violin": {"oscillator": "fmsine", "attack": 0.1, "...": "..."}},
  "bars": [
    {"index": 0, "chord": "Am7", "parts": {
      "violin": {"instrument": "violin", "bar": 0,
                 "notes": [{"pitch": 69, "start": 0.0, "dur": 0.5, "vel": 84}],
                 "patch": null}
    }}
  ]
}
```

**Errors** — `502` when the bandleader cannot produce a usable plan.

## `POST /api/export/midi`

Takes a `Song` (the same shape `/api/compose` returns) and responds with a ZIP
of five MIDI stems, one per instrument. Drums are written to GM channel 10;
melodic instruments get a GM program change.

```
Content-Type: application/zip
Content-Disposition: attachment; filename="monsoon-line-stems.zip"
```

## `WS /ws/jam`

The live loop. The browser owns the clock and asks for bars ahead of the
playhead; the server generates and streams them back.

**Client → server**

| Message | Meaning |
|---|---|
| `{"type": "need_bars", "from_bar": 12}` | Buffer is running low; generate through bar 12 + lookahead |
| `{"type": "steer", "energy": 8}` | 1-10 |
| `{"type": "steer", "tempo": 120}` | 40-240 BPM |
| `{"type": "steer", "mood": "pull it back"}` | Free text passed to the bandleader |
| `{"type": "steer", "solo": "flute"}` | Hand out the solo; `null` clears it |
| `{"type": "steer", "drop": ["drums"]}` | Sit instruments out; `[]` brings them back |
| `{"type": "stop"}` | End the set |

**Server → client**

| Message | Meaning |
|---|---|
| `{"type": "session", "id": "...", "tempo": 96}` | Sent on connect |
| `{"type": "cue", "bar": 8, "cue": {...}}` | New `SectionCue` for the coming window |
| `{"type": "bar", "bar": {...}}` | One generated `Bar`, ready to schedule |
| `{"type": "steered", "tempo": 120, "steer": {...}}` | Steering acknowledged |
| `{"type": "error", "detail": "..."}` | Generation failed; the band has stopped producing bars |

The client buffers bars and repeats the previous one if the next arrives late,
so playback never stops on a slow model response.

## MCP tools

`app/mcp/server.py` runs over stdio and exposes the band to any MCP client:

| Tool | Purpose |
|---|---|
| `band_state` | Key, tempo, bar position and recent bars |
| `band_set_tempo` | Set tempo (40-240) and optionally the key |
| `play_bar` | Write one bar for one instrument yourself |
| `set_patch` | Design an instrument's synth voice |
| `band_play` | Hand a direction to the AI players and let them write bars |
| `band_reset` | Clear state, start from bar 0 |

Register it with:

```json
{"mcpServers": {"ai-band": {
  "command": "docker",
  "args": ["compose", "exec", "-T", "api", "python", "-m", "app.mcp.server"]
}}}
```
