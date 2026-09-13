# Fixes

A running log of every bug fixed. Newest on top.

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
