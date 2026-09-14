# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in NARADA, please report it responsibly.

**Do not open a public issue.** Instead, email the maintainer directly or use
GitHub's private vulnerability reporting feature on the repository.

Include:

- A description of the vulnerability
- Steps to reproduce
- The potential impact
- Any suggested fix (optional but appreciated)

We will acknowledge your report within 48 hours and aim to release a fix within
7 days for critical issues.

## Scope

The following are in scope:

- The FastAPI backend (`api/`)
- WebSocket endpoints
- MCP server tools
- Docker configuration and secrets handling
- Authentication and session management

The following are out of scope:

- Third-party LLM provider APIs
- Vulnerabilities in upstream dependencies (report these to the upstream project)
- Denial of service via intentionally large LLM requests (this is a rate-limit
  concern, not a vulnerability)

## Supported Versions

Only the latest version on `main` is actively supported with security updates.

## Security best practices for contributors

- Never commit secrets, API keys, or `.env` files
- Use environment variables for all sensitive configuration
- Validate and sanitize all user input
- Keep dependencies up to date
