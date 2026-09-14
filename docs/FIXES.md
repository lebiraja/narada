# Fixes

A running log of every bug fixed. Newest on top.

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
