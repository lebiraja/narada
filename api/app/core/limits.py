"""Access and cost limits: the API key gate and per-IP Redis counters.

Counters fail open: a Redis blip logs a warning instead of stopping the band.
Client IP is the direct peer; trusting X-Forwarded-For belongs to the Nginx
deployment, not here.
"""

import hmac
import logging

from fastapi import Header, HTTPException, Request, WebSocket
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

log = logging.getLogger(__name__)

HOUR = 3600


class Limits:
    def __init__(self, client: Redis | None = None) -> None:
        self._redis = client or Redis.from_url(get_settings().redis_url, decode_responses=True)

    async def hit(self, key: str, limit: int, window: int) -> bool:
        """Count one use of `key`; False once it passes `limit` within `window` seconds."""
        if limit <= 0:
            return True
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, window)
        except RedisError as exc:
            log.warning("rate limit check for %s failed open: %s", key, exc)
            return True
        return count <= limit

    async def open_socket(self, ip: str) -> bool:
        limit = get_settings().max_sockets_per_ip
        if await self.hit(f"sockets:{ip}", limit, HOUR):
            return True
        await self.close_socket(ip)
        return False

    async def close_socket(self, ip: str) -> None:
        if get_settings().max_sockets_per_ip <= 0:
            return
        try:
            await self._redis.decr(f"sockets:{ip}")
        except RedisError as exc:
            log.warning("socket release for %s failed: %s", ip, exc)

    async def compose_allowed(self, ip: str) -> bool:
        return await self.hit(f"compose:{ip}", get_settings().compose_per_hour, HOUR)


limits = Limits()


def key_matches(given: str | None) -> bool:
    expected = get_settings().api_key
    return not expected or hmac.compare_digest((given or "").encode(), expected.encode())


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not key_matches(x_api_key):
        raise HTTPException(status_code=401, detail="Missing or wrong API key.")


async def compose_quota(request: Request) -> None:
    if not await limits.compose_allowed(_ip(request)):
        raise HTTPException(status_code=429, detail="Compose limit reached; try again later.")


async def admit(socket: WebSocket) -> str | None:
    """Accept the socket, or turn it away with a reason. Returns the client IP
    when admitted; the caller must release it with `limits.close_socket`."""
    await socket.accept()
    if not key_matches(socket.query_params.get("key")):
        await socket.send_json({"type": "error", "detail": "Missing or wrong API key."})
        await socket.close(code=1008)
        return None
    ip = _ip(socket)
    if not await limits.open_socket(ip):
        await socket.send_json({"type": "error", "detail": "Too many open connections."})
        await socket.close(code=1008)
        return None
    return ip


def _ip(connection: Request | WebSocket) -> str:
    return connection.client.host if connection.client else "unknown"
