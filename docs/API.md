# 🔌 API

Base URL: `http://localhost:8000` (behind the prod Nginx: the public origin, same paths).

## Auth and limits

- **API key** — when `API_KEY` is set, every REST route except `/health` needs header `X-API-Key`, and both sockets need `?key=`. Wrong or missing: `401` on REST; sockets send an `error` frame and close with 1008. Blank = open.
- **Per-IP sockets** — at most `MAX_SOCKETS_PER_IP` (3) at once across `/ws/jam` and `/ws/compose`; extra connections get `{"type":"error","detail":"Too many open connections."}` and close 1008.
- **Compose quota** — `COMPOSE_PER_HOUR` (20) per IP across `POST /api/compose` and `/ws/compose`. REST: `429`; WS: an `error` frame.
- **Jam length** — `JAM_MAX_BARS` (600) bars per session.
- Counters live in Redis and fail open if Redis is down. Setting any limit to 0 disables it.

## `GET /health`

```json
{"status": "ok"}
```

## `POST /api/compose`

Brief the bandleader; get back a complete arrangement in one response. This
runs the full band (one leader call + six player calls per bar), so a 32-bar
piece is 190+ model calls and takes a while. Prefer `WS /ws/compose`, which
streams bars as they are written.

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

**Errors** — `502` when the bandleader cannot produce a usable plan; `429`
when the compose quota is spent; `401` on a bad API key; `422` when `brief` is
not 3-600 characters.

## `WS /ws/compose`

Streaming compose. Same band as `POST /api/compose`; the client can start
playing as soon as the plan and first bars arrive. Disconnecting stops the band.

**Client → server** (one message, right after connect)

```json
{"type": "compose", "brief": "a rainy Chennai evening, slow 6/8"}
```

`brief` is 3-600 characters.

**Server → client**

| Message | Meaning |
|---|---|
| `{"type": "plan", "title", "key", "tempo", "time_signature", "kit", "total_bars"}` | First frame; the song's shape |
| `{"type": "bar", "bar": {...}}` | One conducted `Bar`, in order |
| `{"type": "done"}` | Every bar sent |
| `{"type": "error", "detail": "..."}` | Bad brief, quota or key, too many sockets, or generation failed |

## `POST /api/export/midi`

Takes a `Song` (the same shape `/api/compose` returns) and responds with a ZIP
of six MIDI stems, one per instrument. Drums are written to GM channel 10;
melodic instruments get a GM program change.

```
Content-Type: application/zip
Content-Disposition: attachment; filename="monsoon-line-stems.zip"
```

**Errors** — `413` when the song exceeds 128 bars or 20,000 notes.

## `POST /api/songs`

Save a `Song` (same shape `/api/compose` returns) to Postgres.

**Response** `201` — `{"id": "<uuid>"}`

**Errors** — `413` over the export size limits; `422` invalid song.

## `GET /api/songs`

The 50 most recent songs, newest first.

```json
[{"id": "<uuid>", "title": "Monsoon Line", "key": "A minor", "tempo": 68,
  "time_signature": "4/4", "created_at": "2026-10-02T09:30:00Z"}]
```

## `GET /api/songs/{id}`

The full saved `Song`. **Errors** — `404` unknown id; `422` malformed uuid.

## `POST /api/export/audio`

Takes a `Song` and responds with a rendered MP3: the merged MIDI played through
the FluidR3 GM soundfont (`fluidsynth`), then loudness-normalised to -14 LUFS
(`ffmpeg`). Both run inside the `api` image.

```
Content-Type: audio/mpeg
Content-Disposition: attachment; filename="monsoon-line.mp3"
```

**Errors** — `413` over the same size limits as MIDI export; `503` when the
renderer or soundfont is unavailable or the render fails or times out (120 s).

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
| `{"type": "session", "id": "...", "tempo": 96, "key": "A minor", "time_signature": "4/4"}` | Sent on connect |
| `{"type": "cue", "bar": 8, "cue": {...}}` | New `SectionCue` for the coming window |
| `{"type": "bar", "bar": {...}}` | One generated `Bar`, ready to schedule |
| `{"type": "steered", "tempo": 120, "steer": {...}}` | Steering acknowledged |
| `{"type": "error", "detail": "..."}` | Generation failed, the key or socket cap rejected the connection, or `JAM_MAX_BARS` was reached ("Set limit reached") |

The client buffers bars and repeats the previous one if the next arrives late,
so playback never stops on a slow model response. Server-side, a player whose model call fails covers the bar (repeats its last part quietly, drums keep time) and lays out after two covers in a row.

## MCP tools

`app/mcp/server.py` runs over stdio and exposes the band to any MCP client:

| Tool | Purpose |
|---|---|
| `band_state` | Key, tempo, bar position and recent bars |
| `band_set_tempo` | Set tempo (40-240) and optionally the key |
| `play_bar` | Write one bar for one instrument yourself |
| `set_patch` | Design an instrument's synth voice |
| `band_play` | Hand a direction to the AI players and let them write bars |
| `band_reference` | What an instrument can play: articulations, kit pieces, and a chord's tones/scale/avoid-notes |
| `band_set_kit` | Put the drummer behind a standard, room, jazz, brush or orchestra kit |
| `band_reset` | Clear state, start from bar 0 |

Melodic notes may carry an `articulation` (`pizz`, `palm_mute`, `rhodes`, …)
and `slur`. Drum notes name a `piece` (`kick`, `ghost_snare`, `ride_bell`)
instead of a pitch, and inherit that piece's default velocity unless one is
given. Call `band_reference` for the full vocabulary rather than guessing.

Register it with:

```json
{"mcpServers": {"narada": {
  "command": "docker",
  "args": ["compose", "exec", "-T", "api", "python", "-m", "app.mcp.server"]
}}}
```
