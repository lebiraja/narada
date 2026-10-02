# Fixes

A running log of every bug fixed. Newest on top.

## 2026-10-02 — Landing page crashed once the bass joined the band

**Symptom:** `next build` failed prerendering `/` with `TypeError: h[a] is not a function`, and the same crash would hit the landing page in dev.

**Root cause:** `FIGURE` in `web/components/TrackLanes.tsx` was typed `Record<string, ...>` and had no `bass` entry, so `FIGURE["bass"](i)` called `undefined`. No test rendered the component.

**Fix:** `web/components/TrackLanes.tsx` adds a bass figure and types the table `Record<Instrument, ...>`, so a missing player is now a compile error. New `web/components/TrackLanes.test.tsx` renders a lane for every player.

**Verified:** `next build` completes with `/` prerendered; vitest 123 passed; `tsc --noEmit` clean.

## 2026-10-02 — A streamed piece repeated its last bar forever

**Symptom:** After a streamed composition finished, the band kept playing the final bar until Stop was pressed.

**Root cause:** The live loop treats a missing bar as late and repeats the previous one; nothing told it the piece had ended.

**Fix:** `BandEngine.endAt(bars)` in `web/lib/audio/engine.ts` stops the transport once the last bar has played; `web/lib/useCompose.ts` sets it from the plan's `total_bars` and again on `done`.

**Verified:** new engine test (bar 1 is never triggered after `endAt(1)`); vitest 123 passed.

## 2026-10-02 — `wire_check.py` broke when the provider moved into the app lifespan

**Symptom:** `scripts/wire_check.py` failed with `'State' object has no attribute 'provider'`, then hit the compose rate limit from earlier runs.

**Root cause:** The script used `TestClient(app)` without entering it, so the lifespan never built the shared provider. The per-IP compose limit counted its repeated runs in Redis.

**Fix:** `api/scripts/wire_check.py` enters the client as a context manager and now also exercises `/ws/compose`. Run it with `COMPOSE_PER_HOUR=0`.

**Verified:** wire check passes: 6 players per bar, compose WebSocket plan, 2 bars, done; jam stream cue, bar, bar.

## 2026-10-02 — Drums played as pitched beeps, and every voice had its own reverb

**Symptom:** On a fresh clone the drums sounded like short tonal beeps, toms and the open hat were pitch-shifted kicks and snares, and the five instruments sounded like five separate synths rather than one band in a room.

**Root cause:** `web/public/samples/` is empty by default and drums have `browser: null` in `voices.generated.ts`, so drum notes went through a default pitched `Tone.Synth` on MIDI 36/38. With samples present, the 4-anchor drum map let `Tone.Sampler` pitch-shift one hit into others, and `crash.mp3` was mapped to A#2, which is the open-hat note (46), not the crash (49). Each `Voice` also built its own `Tone.Reverb` straight into the destination: no shared space, pan, EQ, compressor or limiter.

**Fix:** `web/lib/audio/mixer.ts` is one mix bus (per-instrument highpass, pan, reverb send; one shared reverb; compressor then limiter). `web/lib/audio/drums.ts` is a synthesised kit with all 23 `PIECES` mapped, and the three hats share one mono synth so closed/pedal chokes open. `voices.ts` takes its output from the mixer and only uses the drum sampler for the four sampled GM notes; `SAMPLE_MAP` crash moved to C#3.

**Verified:** vitest 98 passed (12 new), `tsc --noEmit` clean. How it sounds, and real hat choking, are not verified without a browser.

## 2026-10-02 — The browser played every piece with 4 beats per bar

**Symptom:** A 6/8 or 7/8 piece played at the wrong bar length in the browser, so the band drifted against the bar lines. The MIDI export and the offline MP3s were correct, which hid it. In compose mode the bar counter also ran one ahead of `song.bars[state.bar]`.

**Root cause:** `barSeconds(tempo, beatsPerBar = 4)` defaulted to 4 beats and no caller passed the song's `time_signature`. The loop was scheduled in `"Ns"` seconds, which drifts under a tempo change, and `playSong` placed notes on the raw audio clock while the UI counter ran on the Transport (two clocks). `playSong` also emitted `bar + 1` per tick.

**Fix:** `web/lib/audio/meter.ts` (`parseMeter`) is the one meter definition, mirroring `api/app/core/meter.py`. `web/lib/audio/scheduler.ts:54` now requires `beatsPerBar`. `web/lib/audio/engine.ts` runs both modes through one `startLoop`: Transport `timeSignature`, one `scheduleRepeat(cb, "1m")`, bar length read per callback with `bpm.getValueAtTime`, and start at `+0.1`. Articulation synths are built in the `Voice` constructor, not inside `schedule()`. `web/lib/useJam.ts` starts the loop on the `session` message and reads `time_signature`.

**Verified:** vitest 86 passed (4/4 = 2.0 s, 3/4 = 1.5 s, 6/8 = 1.5 s, 7/8 = 1.75 s at 120 bpm, in both compose and live), `tsc --noEmit` clean. Real audio timing in a browser is not yet verified. The backend `session` message does not yet send `time_signature`, so live jam is still 4/4 until that half lands.

## 2026-09-14 — A raw network error escaped the provider's retry handler

**Symptom:** Found by a test written to prove the new cover-for-a-lost-bar
behaviour survives a real transport failure. An `httpx.ConnectError` raised
below the OpenAI client propagated straight out of `LLMProvider.structured`,
past the retry loop and past `InstrumentAgent`'s `GenerationError` handler,
crashing the composition.

**Root cause:** The retry handler caught `APIError`, which covers what the
OpenAI client wraps, but not `httpx.HTTPError` — a refused connection, DNS
failure or dropped socket underneath it. Live runs happened not to hit this
because the client wrapped the errors they produced.

**Fix:** `api/app/core/provider.py:79` now catches `httpx.HTTPError` too, so
any transport failure becomes a `GenerationError` and the player covers the
bar instead of the run dying.

**Verified:** `pytest tests/test_resilience.py` — 29 passed, including a
client that raises `ConnectError` directly.

## 2026-09-14 — A player that lost a bar fell silent instead of covering

**Symptom:** During a live agent composition the keys dropped out for three
separate bars mid-piece. With no bass in this band the keys are the harmonic
floor, so the arrangement briefly had no bottom at all. The drums and guitar
vanished in other bars the same way.

**Root cause:** `InstrumentAgent.play` returned an empty `BarPart` on
`GenerationError`. That is the right shape for a first bar with no history,
but on a rate-limited provider it happens routinely mid-piece, and silence is
rarely the most musical answer — a player who loses their place covers rather
than stops.

**Fix:** `_cover()` at `api/app/agents/instrument.py:63`. Sustaining
instruments hold what they last played at 85% velocity; the drummer falls
back to plain time (kick, hat, backbeat) rather than repeating a bar, since
repeating would re-trigger whatever fill was in it. A player with no history
still returns silence, and a tacet player stays tacet — silence the bandleader
asked for is not a failure to paper over.

**Verified:** `pytest tests/test_agents.py` — 26 passed, covering the hold,
the velocity drop, the drum special case, the no-history case and the tacet
case.

## 2026-09-14 — Power chords did not parse

**Symptom:** `parse_chord("E5")` returned None, so a bar marked `E5` was
treated as having no fixed harmony. Every player lost its chord tones, scale
and avoid-notes for that bar. Found while writing a heavy piece, where the
power chord is the most common symbol there is.

**Root cause:** `_QUALITY_TOKENS` had no entry for `5`, and the extension
regex read the `5` of `E5` as part of a numeric extension. `add9`, the jazz
shorthand `C-` for minor, and `Cø` for half-diminished were missing too.

**Fix:** Added `Quality.POWER` (root and fifth, no third) at
`api/app/core/theory.py:38`, with aeolian as its default mode and no
avoid-notes — a chord that states no third forbids neither. Power chords take
no extensions. Added `add9`, `-` and `ø` to the token table.

**Verified:** `pytest tests/test_theory.py` — 63 passed, including that a
power chord contains neither third and that its scale is playable.

## 2026-09-14 — Seven failures found by running real agents against Groq

Everything below was invisible until real models were pointed at the pipeline.
Unit tests with fake providers passed throughout.

**1. Capitalised instrument names invalidated a whole plan.** A bandleader
returning `"Flute"` failed enum validation and threw away an otherwise perfect
32-bar arrangement. Fixed with `Instrument._missing_` and an alias table at
`api/app/core/schema.py:20` — "Flute", "Piano", "Drum Kit", "fiddle" all resolve.

**2. The bandleader invented instruments the band does not have.** It assigned
parts to Trumpet, Trombone and Alto Sax because the prompt never stated the
roster in the schema's own vocabulary. Fixed by naming the five players
explicitly in `_ROSTER` (`prompts.py:15`) and by dropping unknown instruments
instead of failing the plan (`coerce_instruments`).

**3. One bad note silenced a whole bar.** A note at `start: 1.0` — the downbeat
of the *next* bar — failed validation and took the other three notes with it.
`salvage_notes` (`schema.py:92`) now keeps what the model got right and clamps
what is unambiguous, the way out-of-range pitches were already handled.

**4. A 400 from the provider killed the run.** `GenerationError` only covered
parse failures, so an API-level error propagated out of the orchestrator.
The provider now catches `APIError` too and retries once.

**5. Rate-limit retries ignored the provider's own advice.** Groq replies
"try again in 9.6s"; we waited 0.4s and failed again. `retry_after`
(`provider.py:96`) reads the Retry-After header or parses the message.

**6. Five parallel players saturated the token budget instantly.** Each call
cost ~4000 tokens against an 8000 TPM limit. Two fixes: `LLM_MAX_CONCURRENCY`
gates simultaneous calls, and `LLM_PLAYER_EFFORT=low` cut per-call cost from
1350 tokens to 232 — 5.8x cheaper for the same musical output, because per-bar
players need to be quick and in time, not deep.

**7. Every piece came back in 4/4.** The composer prompt's JSON example
hardcoded `"time_signature": "4/4"`, so the model copied it and ignored an
explicit 6/8 request. The example now lists alternatives and the prompt says a
named meter is not a suggestion.

**Verified:** 118 API tests pass, including 28 new resilience tests covering
every case above. A 20-bar piece then composed end to end in 6/8 with all five
players — `output/Restless Monsoon Night.mp3`.

## 2026-09-14 — MCP errors leaked Pydantic tracebacks; hand-written bars had no chord

**Symptom:** `play_bar` rejections returned raw validation dumps including
`https://errors.pydantic.dev/...` URLs — noise for a calling agent. Separately,
bars written through MCP were stored as `"N.C."` with no way to state the
harmony, so the AI players had no context when filling in around them.

**Root cause:** `except (ValueError, ValidationError)` with the message
interpolated directly. `ValidationError` subclasses `ValueError`, so ordering
also mattered — catching `ValueError` first swallowed every validation failure
and misreported it as an unknown instrument.

**Fix:** `_explain()` at `api/app/mcp/server.py:22` renders at most three
problems in plain language; handlers catch `ValidationError` before
`ValueError`; `play_bar` takes an optional `chord`; and writing an earlier bar
no longer rewinds `next_bar`.

**Verified:** `pytest tests/test_mcp.py` — 24 passed, including assertions that
no `https://` appears in any rejection message.

## 2026-09-13 — MIDI export ignored the time signature

**Symptom:** A 6/8 piece exported to stems played back at the wrong speed and
in the wrong meter. Every bar was rendered as four quarter-note beats
regardless of what `Song.time_signature` said, and the files carried no
`time_signature` meta message, so a DAW opened them as 4/4.

**Root cause:** `midi.py` had a module constant `BEATS_PER_BAR = 4` used
directly in the tick conversion. `Song.time_signature` was validated, stored
and returned by the API, but nothing downstream ever read it.

**Fix:** Added `parse_time_signature` and `beats_per_bar` at
`api/app/core/midi.py:24`; `_ticks` now takes the bar length as an argument,
and `instrument_track` writes a real `time_signature` meta message. A 6/8 bar
is three quarter-note beats, not four, which is the unit `Note.dur` counts in.

**Verified:** `docker compose run --rm api pytest tests/test_midi.py` — 11
passed, including a compound-meter bar-length assertion. Confirmed by rendering
"Monsoon Letters" (6/8) end to end: bar positions land correctly on playback.

## 2026-09-13 — Duplicate accessible names in the band meters

**Symptom:** `BandMeters > reports volume changes for the right player` failed
with "Found multiple elements with the text of: Keyboard volume".

**Root cause:** Two causes, one masking the other. Testing Library was not
unmounting between tests, so a `rerender` left the previous tree in the
document; and the change event was dispatched as a raw DOM `change`, which
React's synthetic `onChange` does not observe.

**Fix:** `web/vitest.setup.ts:5` now runs `cleanup` after each test, and
`web/components/BandMeters.test.tsx:44` uses `fireEvent.change`.

**Verified:** `docker compose run --rm web npx vitest run` — 44 passed.

## 2026-09-13 — Web container ignored newly added dependencies

**Symptom:** Every page returned 500 with `Cannot find module
'tailwindcss-animate'`, even after rebuilding the image.

**Root cause:** Two compounding problems. `tailwindcss-animate` was added as a
devDependency although postcss needs it at runtime; and the anonymous
`/app/node_modules` volume from the first `compose up` kept shadowing the
rebuilt image layer, so the new install was never visible.

**Fix:** Moved the package into `dependencies` in `web/package.json`, then
removed the stale volume (`docker compose down web` + `docker volume rm`) so
the container re-creates it from the image.

**Verified:** `curl -o /dev/null -w '%{http_code}' localhost:3000` — 200, and
all four pages render.

## 2026-09-13 — Live jam failures vanished into a background task

**Symptom:** A WebSocket jam session connected and acknowledged steering, but
no bars ever arrived and the client showed nothing — it sat there apparently
live and silent.

**Root cause:** Bar generation ran as a fire-and-forget `asyncio.create_task`.
When the LLM provider raised (a 401 from an unset `LLM_API_KEY`, but equally a
rate limit or timeout), the exception died inside the task. Nothing was logged
to the socket and the client had no way to distinguish "still thinking" from
"the band has stopped".

**Fix:** Wrapped the generator in `_guarded` at `api/app/ws/jam.py:54`, which
logs the traceback and sends `{"type": "error", "detail": ...}` to the client.
`web/lib/useJam.ts:71` now captures it and `web/app/jam/page.tsx:68` renders it.
`asyncio.CancelledError` is re-raised so teardown still works.

**Verified:** Connected to `/ws/jam` with no valid API key and received
`{"type": "error"}` on the socket where previously the connection went silent.

## 2026-09-13 — MIDI stem filenames contained doubled hyphens

**Symptom:** `test_slug_handles_awkward_titles` failed —
`_slug("Monsoon / Line!")` returned `monsoon--line` instead of `monsoon-line`.

**Root cause:** `_slug` stripped punctuation to empty strings and only then
replaced spaces with hyphens, so `" / "` collapsed into two adjacent hyphens.

**Fix:** `api/app/core/midi.py:87` now maps every non-alphanumeric character to
a space and joins on `split()`, which discards runs of whitespace.

**Verified:** `docker compose run --rm api pytest` — 39 passed.
