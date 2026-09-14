# Contributing to NARADA

Thanks for your interest in contributing to NARADA! Whether you're fixing a bug,
adding an instrument voice, improving the frontend, or writing docs — all
contributions are welcome.

## Getting started

1. **Fork** the repo and clone your fork.
2. Copy the environment file and set your LLM key:
   ```bash
   cp .env.example .env
   # edit .env — at minimum set LLM_API_KEY
   ```
3. Start the stack:
   ```bash
   docker compose up -d
   ```
4. Verify everything is healthy:
   ```bash
   docker compose ps   # all four services should show "healthy"
   ```

## Development workflow

| Service | Live reload | How to access |
|---------|------------|---------------|
| API (FastAPI) | Volume-mounted, auto-reloads | http://localhost:8000/docs |
| Web (Next.js) | Volume-mounted, HMR | http://localhost:3000 |

### Running tests

```bash
# Backend (pytest)
docker compose run --rm --no-deps api pytest

# Frontend (vitest)
docker compose run --rm --no-deps web npx vitest run

# End-to-end wire check (stubbed model)
docker compose exec -T -e PYTHONPATH=/app api python scripts/wire_check.py
```

All tests must pass before a PR will be reviewed.

## Submitting a pull request

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature
   ```
2. Make your changes. Keep commits focused and atomic.
3. Run the full test suite (see above).
4. Push to your fork and open a PR against `main`.
5. Fill in the PR template — describe **what** changed and **why**.

### PR guidelines

- **One concern per PR.** A bug fix and a new feature should be separate PRs.
- **Include tests.** If you're adding behaviour, add a test that proves it works.
  If you're fixing a bug, add a test that would have caught it.
- **Update docs.** If your change affects the API, architecture, or user-facing
  behaviour, update the relevant file in `docs/`.
- **No secrets.** Never commit API keys, passwords, or `.env` files.

## Reporting bugs

Open an issue with:

- **What you expected** to happen.
- **What actually happened** (include logs, screenshots, or audio if relevant).
- **Steps to reproduce** — ideally a minimal script or compose override.
- Your OS, Docker version, and which LLM provider you're using.

## Feature requests

Open an issue tagged `enhancement`. Describe the use case, not just the solution.
If you have a design in mind, sketch it out — but we may iterate on the approach.

## Code style

### Python (API)

- Follow PEP 8. We don't enforce a formatter yet, but keep it clean.
- Type hints on all public functions.
- Docstrings for modules and non-obvious functions.
- Use `async`/`await` — the backend is fully async.

### TypeScript (Web)

- Strict mode is on. No `any` unless truly unavoidable.
- Components are functional with hooks.
- Use the existing design tokens and colour system — don't introduce ad-hoc
  colours or fonts.

### Commits

We loosely follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add pan-flute articulation for flute agent
fix: chord parser handles slash chords
test: cover WebSocket reconnection logic
docs: update API.md with new /api/export/stems endpoint
```

## Architecture overview

Before diving in, read [docs/architecture.md](docs/architecture.md) to
understand the agent pipeline, bar generation loop, and how the browser clock
drives playback.

Key things to know:

- **Agents emit notes as data, not audio.** Each instrument agent returns a
  JSON array of notes per bar.
- **The browser owns the clock.** It plays bar *N* while the backend generates
  bar *N+2*.
- **Articulations are registered in Python** and exported to TypeScript via
  `api/scripts/export_voices.py`. Don't hand-edit the generated file.

## Code of Conduct

Be kind, be constructive, be patient. We're building a band — let's keep it
harmonious.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
