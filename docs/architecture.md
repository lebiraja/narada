# 🏗️ Architecture

## Overview

Narada is a web application in which a six-piece band — drums, bass, keyboard,
guitar, flute and violin — is played entirely by AI agents. Each instrument has
its own agent with a musical character and range; a bandleader agent decides
harmony, form, energy, who takes the solo, and writes a shared arrangement
brief per section. The primary actors are the **listener** (a human who briefs
or steers the band), the **bandleader agent**, the six **instrument agents**, a
deterministic **conductor** that tidies every bar, and the **browser audio
engine** that turns the symbolic output into sound. Three surfaces use the same
band: a composer (brief → streamed arrangement), a live jam (continuous
generation steered in real time), and a studio (record a take, export MIDI
stems or an MP3).

## Tech Stack

- **Language:** Python 3.13 (backend), TypeScript 5.9 strict (frontend)
- **Backend:** FastAPI, Pydantic v2, uvicorn, SQLAlchemy 2 (async)
- **Frontend:** Next.js 15 (App Router), React 19, Tailwind CSS, Zod at API boundaries, ESLint
- **Audio (browser):** Tone.js — single Transport clock, synth/sampler voices, synthesised drum kit, shared mix bus, recorder
- **Audio (server):** fluidsynth + FluidR3 GM soundfont + ffmpeg (MP3 export)
- **Cache / live state / limits:** Redis (jam sessions, bar history, per-IP counters)
- **Database:** PostgreSQL via asyncpg (`songs` table)
- **AI:** any OpenAI-compatible chat-completions endpoint (Claude, GPT, Groq, Ollama)
- **MIDI:** mido (stems, merged render input)
- **Agent interop:** MCP (`mcp` SDK) exposing the band as tools
- **Infra:** Docker Compose; Nginx reverse proxy in production; GitHub Actions CI

## Services & Responsibilities

| Service / module | Role |
|---|---|
| `web` | Next.js UI and the entire audio engine; owns the transport clock (counted in bars) |
| `api` | FastAPI: compose (REST + WS), exports, songs, live jam WebSocket |
| `nginx` | Prod only: single published port, WS upgrade, coarse request throttle |
| `app.agents.bandleader` | Plans songs (sections + `ArrangementBrief`); issues section cues during live play |
| `app.agents.instrument` | One agent per instrument; writes one bar on an integer step grid; covers when the model fails |
| `app.agents.orchestrator` | `play_bar`: rhythm layer, then melody layer, then conductor; `compose` / `compose_stream` |
| `app.core.provider` | Shared `LLMProvider` (built in lifespan): structured JSON, retry-with-error, rate-limit waits |
| `app.core.schema` | The musical contract shared by backend, frontend and MCP |
| `app.core.meter` | Time signature to beats and grid steps per bar |
| `app.core.theory` | Chord symbols to pitch sets: chord tones, modes, tensions, per-instrument registers |
| `app.core.articulation` | Per-instrument voices and what each means for MIDI and the browser |
| `app.core.kit` | The drum kit by name — pieces, velocities, kit selection |
| `app.core.conductor` | `conduct` (deterministic bar clean-up), `critique` (findings), `feedback_for` |
| `app.core.metrics` | Ensemble metrics: clash rate, chord-tone-on-strong-beat, register overlap, groove consistency |
| `app.core.session` | Live jam state in Redis; listener steering |
| `app.core.midi` | Renders a Song into per-instrument MIDI stems |
| `app.core.render` | Song to MP3 via fluidsynth + ffmpeg (120 s timeout) |
| `app.core.limits` | Optional API key gate; per-IP socket cap and compose quota in Redis (fail open) |
| `app.db` | Async SQLAlchemy engine, `SongRow`, `get_db` |
| `app.api.songs` | Save, list, fetch songs |
| `app.mcp.server` | Exposes the band as MCP tools for any MCP client |
| `redis` | Live session state, bar history, rate-limit counters |
| `postgres` | Persistence for saved songs |

## Full Application Flow (ASCII)

```text
 LISTENER
    │ brief / steer
    ▼
┌──────────────────────────────────────────────────────────┐
│ BROWSER (Next.js)                                        │
│  /compose        /jam           /studio                  │
│  useCompose(ws)  useJam(ws)     recorder                 │
│      └──────────────┴──────────────┘                     │
│                     ▼                                    │
│  BandEngine (Tone.js) ── one Transport, counted in bars  │
│   BarBuffer · 6 Voices · Mixer · Recorder                │
└─────┬───────────────────┬────────────────────┬───────────┘
      │ WS /ws/compose    │ WS /ws/jam         │ POST export
      │ plan, bar, done   │ need_bars, steer   │ /api/export/*
      │                   │ cue, bar           │ /api/songs
      ▼                   ▼                    ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI  (key check → per-IP limits)                     │
│                                                          │
│ Bandleader ── SongPlan / SectionCue + ArrangementBrief   │
│      │                                                   │
│      ▼  for every bar (BandOrchestrator.play_bar)        │
│ ┌────────────────────────────────────┐                   │
│ │ RHYTHM  drums bass keys guitar     │ in parallel       │
│ └──────────────────┬─────────────────┘                   │
│                    ▼ rhythm bar is shown to              │
│ ┌────────────────────────────────────┐                   │
│ │ MELODY  flute violin               │ in parallel       │
│ └──────────────────┬─────────────────┘                   │
│                    ▼                                     │
│ Conductor.conduct ──► Bar ──► streamed to the client     │
│                                                          │
│ LLMProvider ──► OpenAI-compatible endpoint               │
│ SessionStore / Limits ──► Redis                          │
│ SongRow ──► Postgres      midi / render ──► zip / MP3    │
└──────────────────────────────────────────────────────────┘
```

Blocking `POST /api/compose` runs the same `compose_stream` and collects the
bars into one `Song`.

## Backend Architecture (ASCII)

```text
┌─────────────────────────────────────────────────────┐
│ ROUTERS (auth: X-API-Key / ?key=)                   │
│ api/compose  api/export  api/songs                  │
│ ws/compose   ws/jam      mcp/server                 │
└───┬─────────────┬───────────────┬───────────────┬───┘
    ▼             │               ▼               ▼
┌──────────────┐  │      ┌──────────────┐  ┌───────────┐
│ AGENT LAYER  │  │      │ SESSION      │  │ limits.py │
│ orchestrator │  │      │ JamSession   │  │ per-IP    │
│  bandleader  │  │      │ SessionStore │  │ counters  │
│  instrument  │  │      │ apply_steer  │  └─────┬─────┘
│   ×6         │  │      └──────┬───────┘        │
└───┬──────┬───┘  │             │                │
    │      ▼      ▼             ▼                ▼
    │  ┌───────────────┐   ┌─────────────────────────┐
    │  │ conductor     │   │         Redis           │
    │  │ metrics       │   └─────────────────────────┘
    │  │ theory meter  │
    │  │ articulation  │   ┌─────────────────────────┐
    │  │ kit midi      │   │ db.py ─► Postgres       │
    │  │ render        │   │ (api/songs only)        │
    │  └───────────────┘   └─────────────────────────┘
    ▼
┌──────────────────┐
│ provider.py      │ one shared instance, app.state
└────────┬─────────┘
         ▼
 external model endpoint

 schema.py is depended on by every layer above.
 mcp/server.py reuses orchestrator + SessionStore directly.
```

## Data Models

- **Note** — `pitch` (MIDI 0-127), `start` (0.0-1.0 within the bar), `dur` (in bars), `vel` (optional), plus:
  - `step` / `len` — the integer grid position and length a player writes; the player agent converts them to `start` / `dur` for the bar's step count.
  - `articulation` — how it is played: `pizz`, `tremolo`, `palm_mute`, `slap`, `rhodes`, `staccato`, `ghost`… Unknown values fall back to the instrument's normal voice rather than failing.
  - `piece` — drums only: a named kit surface (`kick`, `ghost_snare`, `ride_bell`) which supplies the pitch and a default velocity.
  - `slur` — play legato into the next note.
- **Patch** — an agent-authored synth voice: oscillator, ADSR, filter, reverb, delay. A validated shape, never executable code.
- **BarPart** — one instrument's notes for one bar, plus an optional patch. Out-of-range pitches are dropped, not rejected.
- **Bar** — `index`, `chord`, and a `BarPart` per instrument.
- **Feel** — key, tempo, time signature; given to every player before it writes.
- **ArrangementBrief** — the section's shared score, all fields optional and leniently parsed: `groove` (kick/snare/hat steps), `bass_rhythm`, `comp_rhythm`, `motif` (scale degrees on the grid), `motif_development`, per-instrument `roles` (register, doubles, entry bar), `energy_curve`, `call_response`.
- **SectionCue** — the bandleader's instruction: section, chords, energy, density, soloist, tacet list, direction, optional `brief`. `SectionPlan` adds `bars`.
- **SongPlan** — title, key, tempo, time signature, kit, and 1-16 `SectionPlan`s.
- **Song** — title, key, tempo, time signature, `kit` (standard/room/jazz/brush/orchestra), per-instrument patches, ordered bars.
- **SongRow** (Postgres `songs`) — `id` uuid, `title`, `key`, `tempo`, `time_signature`, `kit`, `song` (full Song as JSONB), `created_at` (indexed). Tables are created by `create_all` at start-up; no migrations yet.
- **JamSession** — live state in Redis: key, tempo, time signature, next bar, current cue, steering, rolling bar history.

Relationships: a `Song` has many `Bar`s; a `Bar` has up to six `BarPart`s, one
per `Instrument`; a `SectionCue` governs a window of consecutive `Bar`s and may
carry one `ArrangementBrief`; a `JamSession` holds one current `SectionCue` and
a rolling window of `Bar`s.

## Generation Pipeline

1. **Plan** — the leader returns a `SongPlan`; each section carries an `ArrangementBrief` (groove, bass and comp rhythm, motif, roles) so players commit to one score instead of improvising independently.
2. **Rhythm layer** — drums, bass, keys, guitar play the bar in parallel (`RHYTHM_LAYER`), bound to the brief.
3. **Melody layer** — flute and violin play next and see the finished rhythm bar (`MELODY_LAYER`).
4. **Conductor** — `conduct` runs on every bar inside `play_bar`: quantize, register, harmony (strong-beat chord tones), dedupe, clash removal, dynamics (polyphony caps, accompany under a soloist, flute breath).
5. **Context** — each player sees the last `HISTORY_BARS = 4` bars.
6. **Concurrency** — a semaphore (`LLM_MAX_CONCURRENCY`) bounds simultaneous model calls.
7. **Resilience** — the provider retries up to 3 times, feeding the validation error back, and waits out rate limits (max 30 s). A player whose call still fails covers: sustaining instruments repeat their last part at 85% velocity, drums keep plain time, and after `MAX_COVERS = 2` bars in a row the player lays out. Sampling temperature is per role (drums/bass 0.5, keys/guitar 0.7, flute/violin 0.8).

**Known gaps.** `critique` / `feedback_for` (and `scripts/ensemble_report.py`,
which scores finished songs with `core/metrics.py`) exist, but the critic is
not wired into generation: no instrument is regenerated from its findings yet.
The frontend does not call `/api/songs` yet; saved songs are API-only.

## Musical Knowledge

Three modules give the players knowledge they used to have to guess at.

**Harmony** (`core/theory.py`). Chord symbols are parsed into pitch sets, so
each per-bar prompt carries actual notes rather than a symbol the model has to
interpret: `Chord Am9. Chord tones: A C E G B. Scale: A B C D E F# G. Colour
notes: D F#. Avoid landing on: F. Your register this bar: MIDI 59-96.`
Unparseable symbols and `N.C.` mean "no fixed harmony", not an error.

**Registers.** Each player is given a slice of its range so six instruments
do not crowd the same octave — bass at the bottom, keys wide, flute at the top. A soloist
gets a wider window than an accompanist.

**Articulations** (`core/articulation.py`). One table, three consumers: the
prompts describe the options, MIDI export maps them to real soundfont presets,
and the browser approximates them with per-articulation envelopes. A violin
marked `pizz` genuinely switches to the pizzicato patch (GM 45) and back.

| Instrument | Voices |
|---|---|
| violin | sustain, pizz, tremolo, harp |
| flute | flute, recorder, pan flute |
| bass | finger, pick, slap, palm mute, upright |
| guitar | clean, nylon, palm mute, harmonics, 12-string, overdrive |
| keys | grand, Rhodes, FM electric, harpsichord, bright |
| drums | normal, ghost, accent — plus the kit itself |

Any melodic instrument may also use `staccato`, `accent` or `ghost`, which
reshape a note without changing its timbre.

The frontend's copy of this table is **generated**, not written twice:
`api/scripts/export_voices.py` emits `web/lib/audio/voices.generated.ts`, so
the browser and the MIDI exporter cannot drift apart.

**The kit** (`core/kit.py`). 23 named surfaces mapped to General MIDI, each
with the velocity it is normally struck at — a `ghost_snare` is the same drum
as a `snare` at velocity 28. Aliases absorb what a model actually writes
(`bass drum`, `hihat`, `rimshot`). Unknown names are dropped rather than
silently turned into a kick.

## External Integrations

- **LLM endpoint** — any OpenAI-compatible `/chat/completions` service, selected by `LLM_BASE_URL`. Two model tiers: a strong one for the bandleader, a fast one for per-bar players. `reasoning_effort` is sent only when configured.
- **MCP server** (`app/mcp/server.py`) — exposes `band_state`, `band_set_tempo`, `play_bar`, `set_patch`, `band_play`, `band_reference`, `band_set_kit`, `band_reset` over stdio so any MCP client can play the band directly.
- **fluidsynth / ffmpeg / FluidR3 GM** — installed in the `api` images; used only by `POST /api/export/audio`.
- **Sample assets** — optional CC0/CC-BY instrument samples fetched by `scripts/fetch-samples.sh` into `/samples/<instrument>/`, served from our own origin. Without them every voice is a synth and the drums are fully synthesised; nothing is fetched from a third-party CDN at runtime.

## Environment & Config

```text
# Database
DATABASE_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

# Cache / live state
REDIS_URL

# App
SECRET_KEY
CORS_ORIGINS          # comma-separated browser origins
API_KEY               # optional; blank = open. REST X-API-Key, sockets ?key=

# Limits (per client IP, Redis; 0 disables)
MAX_SOCKETS_PER_IP    # default 3
COMPOSE_PER_HOUR      # default 20 (429 on REST, error frame on WS)
JAM_MAX_BARS          # default 600

# Model access
LLM_BASE_URL          # any OpenAI-compatible endpoint
LLM_API_KEY
LLM_MODEL_LEADER      # strong model, plans songs and cues
LLM_MODEL_PLAYER      # fast model, runs every bar x 6
LLM_MAX_CONCURRENCY   # simultaneous player calls, default 5
LLM_PLAYER_EFFORT     # reasoning effort, default low; blank omits
LLM_LEADER_EFFORT

# Audio export
SOUNDFONT_PATH        # default /usr/share/sounds/sf2/FluidR3_GM.sf2

# Frontend (NEXT_PUBLIC_* baked in at build for prod)
NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL
NEXT_PUBLIC_API_KEY   # optional; read by web/lib/api.ts, not in .env.example
```
