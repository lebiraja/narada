# Docker

Everything runs in containers. There is no bare-metal path.

## Services

| Service | Image / build | Port | Depends on |
|---|---|---|---|
| `postgres` | postgres:17-alpine | — | — |
| `redis` | redis:7-alpine | — | — |
| `api` | `./api` (python:3.13-slim, plus fluidsynth, ffmpeg, FluidR3 GM soundfont) | 8000 | postgres, redis (healthy) |
| `web` | `./web` (node:22-slim) | 3000 | api (healthy) |
| `nginx` | nginx:1.27-alpine (prod file only) | 80 | api, web (healthy) |

Every service has a healthcheck, and `api` and `web` wait on
`condition: service_healthy` rather than mere start-up. Credentials come from
`env_file: .env` — nothing is hardcoded in the compose file.

## Running

```bash
cp .env.example .env          # then set LLM_API_KEY
./scripts/fetch-samples.sh    # optional; synth fallback works without it
docker compose up -d
docker compose ps             # all four dev services should read (healthy)
```

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

## Tests

```bash
docker compose run --rm --no-deps api pytest          # 334 tests
docker compose run --rm --no-deps web npx vitest run  # 123 tests
docker compose run --rm --no-deps web npx tsc --noEmit
docker compose run --rm --no-deps web npm run lint
```

CI (`.github/workflows/ci.yml`, on push to main and on PRs) runs `ruff check`
and `pytest` for `api`, and `tsc --noEmit` and `vitest run` for `web`.

`--no-deps` skips booting postgres and redis for suites that do not need them.

For an end-to-end pass against the real app with a stubbed model — routers,
orchestrator, MIDI rendering and the jam socket in one run:

```bash
docker compose exec -T -e PYTHONPATH=/app api python scripts/wire_check.py
```

If a newly added npm package is missing at runtime, the anonymous
`node_modules` volume is shadowing the rebuilt image. Remove it and let the
container re-create it:

```bash
docker compose down web
docker volume ls -q | grep let-band-this | xargs -r docker volume rm
docker compose up -d web
```

## Production

`docker-compose.prod.yml` swaps the dev images for `api/Dockerfile.prod` and
`web/Dockerfile.prod`, drops every source bind mount, adds
`restart: unless-stopped`, and publishes only Nginx on port 80.

```bash
# .env: NEXT_PUBLIC_API_URL / NEXT_PUBLIC_WS_URL = the public origin
# (e.g. https://band.example.com, wss://band.example.com)
docker compose -f docker-compose.prod.yml up -d --build
```

- `api` (Dockerfile.prod): multi-stage, pinned requirements only (no dev deps), runs as non-root user `band`, uvicorn without `--reload` and with `--proxy-headers`. Still includes fluidsynth, ffmpeg and the FluidR3 soundfont for MP3 export.
- `web` (Dockerfile.prod): `npm ci`, `next build`, `next start`, as user `node`. `NEXT_PUBLIC_*` are build args baked into the client bundle, so changing them needs a rebuild.
- `nginx` (`nginx/nginx.conf`): proxies `/api/` (900 s read timeout, for blocking compose), `/ws/` (WebSocket upgrade, 3600 s timeouts), `/health` and `/` to `web`; 10 req/s per-IP throttle (burst 20) on `/api/` and `/ws/`; 2 MB body limit. TLS is not terminated here [?].
- The app's per-IP limits read the direct peer address; behind Nginx that is the proxy unless the app is changed to trust `X-Forwarded-For` (uvicorn runs with `--forwarded-allow-ips "*"`).

## Volumes

`pgdata` and `redisdata` persist across restarts. The `api` and `web` source
trees are bind-mounted for hot reload; `node_modules` and `.next` are masked by
anonymous volumes so the container's own installs are not shadowed by the host.

## Notes

- Services address each other by Docker network name (`postgres`, `redis`, `api`) — never `localhost`.
- The browser reaches the API via `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`, which point at the published host ports.
- The dev images run dev servers with reload; use the prod compose file for built images.
- The `api` tables are created at start-up (`create_all`); there are no migrations yet.
