# Architecture

## Overview

Narada is a web application in which a five-piece band — drums, keyboard,
guitar, flute and violin — is played entirely by AI agents. Each instrument has
its own agent with a musical character and range; a bandleader agent decides
harmony, form, energy and who takes the solo. The primary actors are the
**listener** (a human who briefs or steers the band), the **bandleader agent**,
the five **instrument agents**, and the **browser audio engine** that turns
their symbolic output into sound. Three surfaces use the same band: a composer
(brief → full arrangement), a live jam (continuous generation the listener
steers in real time), and a studio (record a take, export audio and MIDI stems).

## Tech Stack

- **Language:** Python 3.13 (backend), TypeScript 5.9 (frontend)
- **Backend:** FastAPI, Pydantic v2, uvicorn
- **Frontend:** Next.js 15 (App Router), React 19, Tailwind CSS
- **Audio:** Tone.js — Web Audio transport, samplers, synths, recorder
- **Cache / live state:** Redis (jam sessions, bar history)
- **Database:** PostgreSQL (saved songs and takes — reserved, not yet written to)
- **AI:** any OpenAI-compatible chat-completions endpoint (Claude, GPT, Groq, Ollama)
- **MIDI:** mido (server-side stem rendering)
- **Agent interop:** MCP (`mcp` SDK) exposing the band as tools
- **Infra:** Docker Compose

## Services & Responsibilities

| Service / module | Role |
|---|---|
| `web` | Next.js UI and the entire audio engine; owns the transport clock |
| `api` | FastAPI: compose endpoint, MIDI export, live jam WebSocket |
| `app.agents.bandleader` | Plans songs; issues section cues during live play |
| `app.agents.instrument` | One agent per instrument; writes one bar at a time |
| `app.agents.orchestrator` | Runs the five players in parallel per bar |
| `app.core.provider` | Model access over any OpenAI-compatible endpoint |
| `app.core.schema` | The musical contract shared by backend, frontend and MCP |
| `app.core.theory` | Chord symbols to real pitch sets: chord tones, modes, tensions, registers |
| `app.core.articulation` | How each instrument can change voice, and what that means for MIDI and the browser |
| `app.core.kit` | The drum kit by name — pieces, velocities, and kit selection |
| `app.core.session` | Live jam state in Redis; listener steering |
| `app.core.midi` | Renders a Song into per-instrument MIDI stems |
| `app.mcp.server` | Exposes the band as MCP tools for any MCP client |
| `redis` | Live session state and recent bar history |
| `postgres` | Persistence for saved work |

## Full Application Flow (ASCII)

```text
 LISTENER
    │ brief / steer
    ▼
┌──────────────────────────────────────────────────────────┐
│ BROWSER (Next.js)                                        │
│   /compose      /jam          /studio                    │
│      │            │              │                       │
│      │        useJam(ws)     recorder                    │
│      └────────────┴──────────────┘                       │
│                   ▼                                      │
│         BandEngine (Tone.js) ── owns the clock           │
│           BarBuffer · 5 Voices · Recorder                │
└─────┬────────────────────────────────┬───────────────────┘
      │ POST /api/compose              │ WS /ws/jam
      │ POST /api/export/midi          │  ↑ need_bars, steer
      ▼                                ▼  ↓ cue, bar, error
┌──────────────────────────────────────────────────────────┐
│ FastAPI                                                  │
│      │                                                   │
│      ▼                                                   │
│ BandOrchestrator                                         │
│   ┌── Bandleader ── SectionCue (chords, energy, solo)   │
│   │                     │                                │
│   │        ┌────────────┴────────────┐                   │
│   │        ▼   5 players, in parallel ▼                  │
│   │   drums  keys  guitar  flute  violin                 │
│   │        └────────────┬────────────┘                   │
│   │                     ▼                                │
│   │                   Bar(notes, patches)                │
│   └─────────────────────┼────────────────────────────────┘
│                         ▼                                │
│  LLMProvider ──► any OpenAI-compatible endpoint          │
│  SessionStore ──► Redis (cue, history, steering)         │
│  midi.stems_zip ──► 5 .mid files                         │
└──────────────────────────────────────────────────────────┘
```

## Backend Architecture (ASCII)

```text
┌─────────────────────────────────────────────────────┐
│  ROUTERS                                            │
│  api/compose.py   api/export.py   ws/jam.py         │
└────────┬───────────────┬───────────────┬────────────┘
         │               │               │
         ▼               │               ▼
┌──────────────────┐     │      ┌──────────────────┐
│ AGENT LAYER      │     │      │ SESSION LAYER    │
│ orchestrator ──┐ │     │      │ JamSession       │
│  bandleader    │ │     │      │ SessionStore     │
│  instrument ×5 │ │     │      │ apply_steer      │
└────────┬───────┘ │     │      └────────┬─────────┘
         │         │     │               │
         ▼         │     ▼               ▼
┌──────────────┐   │  ┌──────────┐   ┌───────┐
│ provider.py  │   └─►│ midi.py  │   │ Redis │
│ (LLM client) │      └──────────┘   └───────┘
└──────┬───────┘
       ▼
 external model endpoint

  schema.py is depended on by every layer above
  mcp/server.py sits beside the routers, reusing
  orchestrator + SessionStore directly
```

## Data Models

- **Note** — `pitch` (MIDI 0-127), `start` (0.0-1.0 within the bar), `dur` (in bars), `vel` (optional), plus:
  - `articulation` — how it is played: `pizz`, `tremolo`, `palm_mute`, `harmonics`, `rhodes`, `recorder`, `staccato`, `accent`, `ghost`… Unknown values fall back to the instrument's normal voice rather than failing.
  - `piece` — drums only: a named kit surface (`kick`, `ghost_snare`, `ride_bell`) which supplies the pitch and a default velocity, so an agent never writes a General MIDI number.
  - `slur` — play legato into the next note.
- **Patch** — an agent-authored synth voice: oscillator, ADSR, filter, reverb, delay. A validated shape, never executable code.
- **BarPart** — one instrument's notes for one bar, plus an optional patch. Out-of-range pitches are dropped, not rejected, so one bad note never kills a bar.
- **Bar** — `index`, `chord`, and a `BarPart` per instrument.
- **SectionCue** — the bandleader's instruction: section name, chord list, energy, density, soloist, tacet list, and a one-line direction.
- **Song** — title, key, tempo, time signature, `kit` (standard/room/jazz/brush/orchestra), per-instrument patches, and an ordered list of bars.
- **JamSession** — live state: key, tempo, next bar, current cue, listener steering, and the last four bars as prompt context.

Relationships: a `Song` has many `Bar`s; a `Bar` has up to five `BarPart`s, one
per `Instrument`; a `SectionCue` governs a window of consecutive `Bar`s; a
`JamSession` holds one current `SectionCue` and a rolling window of `Bar`s.

## Musical Knowledge

Three modules give the players knowledge they used to have to guess at.

**Harmony** (`core/theory.py`). Chord symbols are parsed into pitch sets, so
each per-bar prompt carries actual notes rather than a symbol the model has to
interpret: `Chord Am9. Chord tones: A C E G B. Scale: A B C D E F# G. Colour
notes: D F#. Avoid landing on: F. Your register this bar: MIDI 59-96.`
Unparseable symbols and `N.C.` mean "no fixed harmony", not an error.

**Registers.** Each player is given a slice of its range so five instruments
do not crowd the same octave — keys low and wide, flute at the top. A soloist
gets a wider window than an accompanist.

**Articulations** (`core/articulation.py`). One table, three consumers: the
prompts describe the options, MIDI export maps them to real soundfont presets,
and the browser approximates them with per-articulation envelopes. A violin
marked `pizz` genuinely switches to the pizzicato patch (GM 45) and back.

| Instrument | Voices |
|---|---|
| violin | sustain, pizz, tremolo, harp |
| flute | flute, recorder, pan flute |
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

- **LLM endpoint** — any OpenAI-compatible `/chat/completions` service, selected by `LLM_BASE_URL`. Two model tiers: a strong one for the bandleader, a fast one for per-bar players.
- **MCP server** (`app/mcp/server.py`) — exposes `band_state`, `band_set_tempo`, `play_bar`, `set_patch`, `band_play`, `band_reset` over stdio so any MCP client can play the band directly.
- **Sample assets** — CC0/CC-BY instrument samples fetched by `scripts/fetch-samples.sh` and served from our own origin. No third-party CDN at runtime.

## Environment & Config

```text
# Database
DATABASE_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

# Cache / live state
REDIS_URL

# App
SECRET_KEY

# Model access
LLM_BASE_URL          # any OpenAI-compatible endpoint
LLM_API_KEY
LLM_MODEL_LEADER      # strong model, runs every few bars
LLM_MODEL_PLAYER      # fast model, runs every bar × 5

# Frontend
NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL
```
