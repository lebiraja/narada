# Docker

Everything runs in containers. There is no bare-metal path.

## Services

| Service | Image / build | Port | Depends on |
|---|---|---|---|
| `postgres` | postgres:17-alpine | — | — |
| `redis` | redis:7-alpine | — | — |
| `api` | `./api` (python:3.13-slim) | 8000 | postgres, redis (healthy) |
| `web` | `./web` (node:22-slim) | 3000 | api (healthy) |

Every service has a healthcheck, and `api` and `web` wait on
`condition: service_healthy` rather than mere start-up. Credentials come from
`env_file: .env` — nothing is hardcoded in the compose file.

## Running

```bash
cp .env.example .env          # then set LLM_API_KEY
./scripts/fetch-samples.sh    # optional; synth fallback works without it
docker compose up -d
docker compose ps             # all four should read (healthy)
```

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

## Tests

```bash
docker compose run --rm --no-deps api pytest
docker compose run --rm --no-deps web npm run test
docker compose run --rm --no-deps web npx tsc --noEmit
```

`--no-deps` skips booting postgres and redis for suites that do not need them.

## Volumes

`pgdata` and `redisdata` persist across restarts. The `api` and `web` source
trees are bind-mounted for hot reload; `node_modules` and `.next` are masked by
anonymous volumes so the container's own installs are not shadowed by the host.

## Notes

- Services address each other by Docker network name (`postgres`, `redis`, `api`) — never `localhost`.
- The browser reaches the API via `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`, which point at the published host ports.
- Both dev images run dev servers with reload. A production image would build Next.js and drop `--reload` from uvicorn.
