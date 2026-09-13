# Status

## [2026-09-13 17:45] — Docs written, stack verified end to end
**What:** Wrote `docs/architecture.md`, `docs/API.md`, `docs/docker.md`, `docs/FIXES.md` and this log. Confirmed all four containers healthy, all four pages 200, MIDI export returning 5 stems, WebSocket handshake and steering working.
**Why:** Project rules require living docs; verification before claiming completion.
**State:** DONE
**Next:** Set a real `LLM_API_KEY` and listen to an actual composed piece.

## [2026-09-13 17:30] — Live jam errors now reach the client
**What:** Wrapped bar generation in `_guarded` so provider failures are logged and sent as `{"type":"error"}`; surfaced in `useJam` and the jam page.
**Why:** A 401 killed the background task silently — the UI showed "live" forever with no sound and no explanation.
**State:** DONE
**Next:** —

## [2026-09-13 17:15] — Frontend built: landing, composer, jam, studio
**What:** Next.js App Router pages with a dark editorial/brutalist direction (bone on ink, ember accent, mono type, grain overlay). `BandEngine` owns the Tone.js transport; `useBand` and `useJam` hooks bridge React to it. Typecheck clean.
**Why:** The audio engine had to exist and be provably correct before AI output could be heard.
**State:** DONE
**Next:** —

## [2026-09-13 16:50] — MCP instrument server
**What:** `app/mcp/server.py` exposes `band_state`, `band_set_tempo`, `play_bar`, `set_patch`, `band_play`, `band_reset` over stdio, sharing Redis state with live jam sessions.
**Why:** Makes "an AI controls the instruments" literal — any MCP client, including Claude Code, can play the band directly.
**State:** DONE
**Next:** Register in `.mcp.json` and try playing a bar by hand.

## [2026-09-13 16:30] — Backend: agents, orchestrator, live loop, MIDI export
**What:** Bandleader + 5 instrument agents with per-instrument character prompts and MIDI ranges; orchestrator runs the five players in parallel per bar; `/ws/jam` rolling-lookahead loop with Redis session state; `/api/compose`; MIDI stem export via mido. 39 tests passing.
**Why:** Core of the product.
**State:** DONE
**Next:** —

## [2026-09-13 16:00] — Decision: symbolic MIDI + OpenAI-compatible provider layer
**What:** Chose symbolic note generation over raw-audio models; five instrument agents under a bandleader; model access through any OpenAI-compatible endpoint rather than a single vendor SDK; instruments exposed as MCP tools.
**Why:** Symbolic output keeps every instrument independently editable, mutable and exportable, and is fast and cheap enough for a real-time loop. The provider layer means Claude, GPT, Groq or local Ollama all work by config.
**State:** DECIDED
**Next:** —

## [2026-09-13 15:40] — Project scaffolded
**What:** Docker Compose (postgres, redis, api, web) with healthchecks and `env_file`; FastAPI + Next.js skeletons; Pydantic musical schema shared across backend, frontend and MCP.
**Why:** Foundation for everything else.
**State:** DONE
**Next:** —
