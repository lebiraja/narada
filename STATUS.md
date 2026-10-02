# Status

## [2026-10-02 16:45] — Orchestration overhaul: six-player band, score-first arrangement, conductor, streaming compose
**What:** P4 leader writes an `ArrangementBrief` per section (groove, motif, roles, energy curve); rhythm layer (drums, bass, keys, guitar) plays first, melody (flute, violin) hears it; `compose_stream` yields the plan then each bar. P5 `conduct()` quantizes, dedupes, fixes strong-beat harmony, removes clashes, enforces register and ducks under the soloist on every bar (Monsoon clash 0.036 to 0.004, keys/guitar overlap 0.50 to 0.34). P6 bass added end to end. P7 retry-with-error, 3 attempts, per-role temperature, covers fade after 2. P8 `/ws/compose`, `/api/songs` on Postgres, streaming compose UI. P9 CORS from config, optional API key, per-IP socket and compose limits, `jam_max_bars`, size caps, CI, prod Dockerfiles, nginx, Zod, ESLint. Backend 334 passed, frontend 123 passed, wire check OK, `next build` OK.
**Why:** Reviewers said the band was out of sync and badly orchestrated: players were blind to meter and each other, rhythm was floats, the browser played everything in 4/4, drums were beeps, nothing blended.
**State:** DONE, except: critic loop is not wired (a streamed bar cannot be revised after it is sent), soundfont playback in the browser was not adopted (spike stopped), Alembic still to replace `create_all`, the frontend never calls `/api/songs`, and none of it has been heard by a human yet.
**Next:** Listen to a one-minute render and tune the mix values (pans, sends, compressor); Playwright E2E; critic loop for non-streamed compose.

## [2026-10-02 16:20] — P3: players know key, meter, tempo and next chord; rhythm on an integer step grid
**What:** New `Feel` model (key, tempo, time signature) threaded from compose, jam and MCP into every player prompt. Prompt now states key, meter with step count and grouping (7/8 as 3+2+2), this and next chord, position in the section, and the bar's step range with two worked examples. Players write `step`/`len` integers; `_on_grid` converts to `start`/`dur`; legacy floats still accepted. History renders as `pitch@step/len`. Backend suite 273 passed (10 new).
**Why:** Players were blind to meter and wrote floats like 0.333, so onsets between parts drifted and 6/8 and 7/8 bars were guesswork.
**State:** DONE. Unproven with a real model: the harness measures whether on-grid and lock rates actually improve.
**Next:** Run a real-model comparison with the P0 metrics; P4 score-first arrangement.

## [2026-10-02 16:05] — P2c: server-side MP3 export through a real soundfont
**What:** `POST /api/export/audio` renders a song with `fluidsynth` + FluidR3 GM and normalises with `ffmpeg` (new `core/render.py`, merged MIDI in `midi.py:song_to_midi` with one channel per melodic part). `api/Dockerfile` installs the tools and soundfont. Both export routes now return 413 above 128 bars / 20,000 notes. Backend suite 263 passed; a real 2-bar render produced a valid 157 KB MP3 in Docker. `_slug` is now public `slug`.
**Why:** What you export should sound like a real instrument set, not a different engine from playback, and the export routes had no size cap.
**State:** DONE. No UI button yet for the audio export.
**Next:** Soundfont spike in the browser (SpessaSynth against the Tone clock), then a Playwright listen of the mix.

## [2026-10-02 15:55] — P2a: shared mix bus and a real synthesised drum kit
**What:** Added `mixer.ts` (per-instrument highpass/pan/reverb send, one shared reverb, compressor, limiter) and `drums.ts` (23 kit pieces, shared hat synth for choke). Voices now output to the mixer; agent patch `reverb` sets the send. Vitest 98 passed, `tsc` clean. See FIXES.md.
**Why:** Drums were pitched beeps by default and each instrument had its own reverb, so nothing blended.
**State:** DONE (tests). Sound quality and hat choke not yet heard in a browser.
**Next:** P2c server audio export (in progress), then the soundfont spike and a Playwright listen.

## [2026-10-02 15:50] — P1 backend: live jam carries key, meter and tempo
**What:** `JamSession` gained `time_signature`; the `session` message now sends `key` and `time_signature`; the leader's cue prompt now states key, meter and tempo (`bandleader.py:next_cue`, `ws/jam.py`). Backend suite 251 passed.
**Why:** The leader never knew the tempo or meter, and the browser had no way to learn the meter in live mode.
**State:** DONE — plumbing only. A live set is still always 4/4 in A minor because nothing yet chooses a different key or meter.
**Next:** P2 (shared mix bus, real drum sounds, soundfont spike). Letting the leader or user pick key/meter for a jam goes in with P4.

## [2026-10-02 15:35] — P1 frontend: one clock, correct meter
**What:** Added `web/lib/audio/meter.ts`; `barSeconds` now requires `beatsPerBar`; `engine.ts` runs compose and live through one Transport loop in bars with a time signature; synths are built up front in `voices.ts`; `useJam.ts` reads `time_signature` from the `session` message. Vitest 86 passed, `tsc` clean. See FIXES.md.
**Why:** The browser played every piece in 4/4, so 6/8 and 7/8 pieces were the wrong length, and two clocks could drift.
**State:** DONE (frontend). Not yet checked with real audio in a browser.
**Next:** Backend half of P1: `session` message carries `time_signature` and `key`, and the leader picks them. Then P2 (sound and mix bus).

## [2026-10-02 12:00] — P0: ensemble metrics harness and shared meter module
**What:** Added `api/app/core/meter.py` (single source for time-signature maths, moved out of `midi.py`), `api/app/core/metrics.py` (on-grid rate, kick–bass lock, strong-beat chord tones, clash rate, register overlap, groove consistency, empty-beat rate, in-scale rate) and `api/scripts/ensemble_report.py`. 17 new tests; full backend suite 250 passed. Baseline on the hand-written pieces: Monsoon Letters (6/8) on-grid 1.00, kick–bass lock 0.33, strong-beat chord tones 0.80, clash 0.04; Tandava (7/8) on-grid 1.00, kick–bass lock 0.39, strong-beat chord tones 0.99, clash 0.00. Keys/guitar register overlap is 0.50–0.62 on both.
**Why:** "In sync" needs a number before the orchestration changes, so each later phase can be proven. Density-vs-energy was skipped because `Song` does not store energy.
**State:** DONE
**Next:** P1 frontend meter and single clock (in progress); the 90% kick–bass target applies once P6 adds a real bass part.

## [2026-09-14 07:50] — Agents composed with the new vocabulary: "Evening Whisper"
**What:** 18 bars, D minor, 6/8 at 70bpm, written entirely by the agents. They used the articulation system unprompted: violin bowed for 12 bars then pizzicato for the whole closing section (23 pizz notes), keys on Rhodes (35 notes) with occasional bright stabs, 39 ghost notes, and seven named kit pieces including `kick_soft` and `snare_roll` — neither of which appeared in any example I wrote. Output: `output/Evening Whisper.mp3`.
**Why:** The instrument work needed proving by the band itself, not by a hand-written demo.
**State:** DONE
**Next:** Live jam still needs a paid tier — 742s for 18 bars on the free tier.

## [2026-09-14 07:45] — Players cover for a lost bar instead of vanishing
**What:** A provider failure now makes a sustaining player hold its previous notes slightly quieter, and the drummer keep plain time. See FIXES.md.
**Why:** Watching a live composition, the keys — the harmonic floor of a band with no bass — dropped out for three bars because their generation was rate-limited.
**State:** DONE
**Next:** —

## [2026-09-14 07:40] — "Tandava": heavy piece in 7/8
**What:** `api/scripts/compose_tandava.py` — 28 bars in E aeolian, 7/8 at 132bpm, counted 3+2+2. Palm-muted riff doubled across two panned guitar tracks, keys covering bass duty two octaves down (no bass player in the band), drums marking the three accents with ghost notes between, violin entering on tremolo then soaring over the lift. Output: `output/Tandava.mp3`, mastered to -9.0 LUFS.
**Why:** Nothing so far had used an odd meter or driven from the rhythm section, and the new articulations needed a piece that leaned on them hard.
**State:** DONE
**Next:** —

## [2026-09-14 07:38] — Power chords now parse
**What:** Added `Quality.POWER`, plus `add9`, `C-` and `Cø` to the chord parser. See FIXES.md.
**Why:** `E5` was unparseable, so any bar using a power chord silently lost all its harmony guidance.
**State:** DONE
**Next:** —

## [2026-09-14 07:35] — Instruments gained real musical capability
**What:** Three new modules. `core/theory.py` parses chord symbols into chord tones, modes, colour notes and avoid-notes, and assigns each player a register slice — every per-bar prompt now carries actual pitch names instead of a bare chord symbol. `core/articulation.py` gives each instrument real voices (violin: pizz/tremolo/harp; guitar: palm-mute/nylon/harmonics/12-string; keys: Rhodes/FM/harpsichord; flute: recorder/pan flute) mapped to genuine soundfont presets in MIDI export and per-articulation envelopes in the browser. `core/kit.py` replaces raw GM numbers with 23 named kit pieces, each carrying the velocity it is normally struck at, plus kit selection (brush/jazz/room/standard/orchestra).
**Why:** Every violin note sounded like the same violin. A note was only pitch/start/dur/vel, so there was no way to pluck, mute, or strike a ghost note — and the drummer was writing GM numbers by hand and getting them wrong.
**State:** DONE
**Next:** —

## [2026-09-14 07:30] — Frontend articulation table is generated, not duplicated
**What:** `api/scripts/export_voices.py` emits `web/lib/audio/voices.generated.ts` from the Python registry. The browser builds one synth per articulation lazily, so a violin switching bowed→pizzicato within a bar is a different sound rather than the same sound quieter.
**Why:** Hand-maintaining the same table in two languages guarantees drift; the MIDI exporter and the browser must agree on what "pizz" means.
**State:** DONE
**Next:** —

## [2026-09-14 07:20] — Renamed to NARADA, pushed to GitHub
**What:** Renamed throughout (app title, MCP identity, package, page metadata, export filenames, docs) and pushed to github.com/lebiraja/narada. Verified no secret ever entered history.
**Why:** Project needed its name.
**State:** DONE
**Next:** —

## [2026-09-14 00:30] — Agents composed their own piece; seven real bugs fixed
**What:** Wired Groq (`openai/gpt-oss-120b`) and ran the real agents end to end. Found and fixed seven failures invisible to fake-provider tests — instrument-name casing, invented instruments, one-bad-note-kills-the-bar, unhandled API errors, ignored retry-after, token saturation, and hardcoded 4/4. Added 28 resilience tests and 7 MCP tests (118 API tests total). Output: `output/Restless Monsoon Night.mp3`, 20 bars in 6/8 composed entirely by the agents.
**Why:** Everything passed against mocks and failed against a real model on the first call.
**State:** DONE
**Next:** —

## [2026-09-14 00:15] — Live jam measured: blocked by free-tier quota, not architecture
**What:** `scripts/jam_live_check.py` measures generation against the bar budget. On Groq's free tier: 33.5s per bar against 2.5s. Generation itself is ~1.5s for all five players; the rest is waiting on the 8000 TPM ceiling.
**Why:** "Live" was an untested claim. It is a quota problem, not a design problem — the lookahead buffer and bar-repeat fallback behave exactly as designed under starvation.
**State:** BLOCKED — needs a paid tier or a local model to run live.
**Next:** Re-measure on a Dev-tier key or local Ollama.

## [2026-09-14 00:05] — Reasoning effort cut player cost 5.8x
**What:** Added `LLM_PLAYER_EFFORT` (default "low") and `LLM_MAX_CONCURRENCY`. Measured: 1350 tokens at default effort vs 232 at low, same 4 notes.
**Why:** Per-bar players were spending a reasoning budget they do not need; five of them saturated an 8000 TPM limit in one bar.
**State:** DONE
**Next:** —

## [2026-09-13 23:40] — First finished piece: "Monsoon Letters"
**What:** Wrote a 30-second piece directly into the band's schema (`api/scripts/compose_monsoon.py`) — A dorian, 6/8, 84bpm, 16 bars, 328 notes. Exported through the real `/api/export/midi`, merged the five stems to GM voices, rendered with fluidsynth against MuseScore General, and mastered to -11.5 LUFS. Output in `output/`.
**Why:** Nothing had actually been heard end to end. Writing a real piece through the production path is the only way to prove the schema, exporter and voicing choices hold up musically.
**State:** DONE
**Next:** Same path with live agents once an LLM key is set.

## [2026-09-13 23:35] — MIDI exporter now honours time signature
**What:** `midi.py` parsed and applied `Song.time_signature` instead of assuming 4/4, and writes a `time_signature` meta message. Added 5 tests (81 API tests total).
**Why:** Found while exporting a 6/8 piece — every non-4/4 song was silently rendered at the wrong bar length and opened as 4/4 in any DAW.
**State:** DONE
**Next:** —

## [2026-09-13 18:25] — Visual rebuild: stage palette, per-player colour, Magic UI
**What:** Replaced the dark/vermilion scheme with a stage palette (#12100F ground, warm lamp cast) and gave each player a permanent hue used everywhere — meters, sliders, solo buttons, hero lanes. Instrument Serif for display, Inter for UI. The hero is now five animated track lanes (`components/TrackLanes.tsx`) rather than a headline over a gradient. Magic UI supplies BlurFade, NumberTicker, ShineBorder, TextAnimate and AnimatedShinyText. Rewrote all copy in plain sentence case.
**Why:** The first pass leaned on generic AI-design tells — numbered 01/02/03 markers on a non-sequence, all-caps eyebrows, `·`-joined meta strings, `→` on links. Colour-coding the players also solves a real problem: you can read the band without reading labels.
**State:** DONE
**Next:** —

## [2026-09-13 18:05] — Test coverage raised from 48 to 120
**What:** Added `test_mcp.py` (17), `test_api.py` (8), `test_jam.py` (12), `engine.test.ts` (16), `useJam.test.ts` (14), `BandMeters.test.tsx` (5), plus a Tone.js mock and shared fixtures under `web/lib/testing/`. Added `api/scripts/wire_check.py` for an end-to-end pass against the real app with a stubbed model.
**Why:** The MCP server, HTTP routes, WebSocket loop, audio engine and hooks were all untested — precisely the parts that break silently.
**State:** DONE
**Next:** —

## [2026-09-13 17:55] — MCP server and jam socket made injectable
**What:** `app/mcp/server.py` now takes its store and orchestrator through `configure()`; `app/ws/jam.py` builds its dependencies via `make_store`/`make_orchestrator`. Both default to the real thing.
**Why:** The module-level `SessionStore()` opened a Redis connection at import time, which made the MCP tools untestable and coupled importing the module to infrastructure being up.
**State:** DONE
**Next:** —

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
