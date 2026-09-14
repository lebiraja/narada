# NARADA

Five instruments. Five agents. One band.

Drums, keyboard, guitar, flute and violin — each played by its own AI agent,
under a bandleader that decides harmony, form, energy and who takes the solo.

Named for Narada, the sage who travels between worlds with a veena in hand,
carrying messages nobody else can deliver.

- **Composer** — brief the bandleader, get a full five-part arrangement.
- **Live jam** — the band plays continuously while you steer energy, tempo, mood, solos and who sits out.
- **Studio** — record a take, export the audio and five MIDI stems.

The band is also an **MCP server**, so any MCP client (Claude Code included) can
play the instruments directly.

## Run it

```bash
cp .env.example .env          # set LLM_API_KEY
./scripts/fetch-samples.sh    # optional — synth voices work without samples
docker compose up -d
```

- UI — http://localhost:3000
- API docs — http://localhost:8000/docs

## How it works

The browser owns the clock. It plays bar *N* while the backend generates bar
*N+2*: the bandleader issues a section cue, then all five instrument agents
write their bar in parallel, and each bar streams back over a WebSocket. If a
bar arrives late the engine repeats the previous one, so the music never stops.

Agents emit notes as data, not audio — which is why you can mute one
instrument, hand it a solo mid-song, or export it as its own MIDI stem. They
can also design their own synth patches (a validated shape, never executable
code) when they want a different sound.

See [docs/architecture.md](docs/architecture.md) for the full picture and
[docs/API.md](docs/API.md) for the endpoints and MCP tools.

## Tests

```bash
docker compose run --rm --no-deps api pytest          # 76 tests
docker compose run --rm --no-deps web npx vitest run  # 44 tests
```

An end-to-end pass against the real app with a stubbed model:

```bash
docker compose exec -T -e PYTHONPATH=/app api python scripts/wire_check.py
```
