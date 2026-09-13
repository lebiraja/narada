# Fixes

A running log of every bug fixed. Newest on top.

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
