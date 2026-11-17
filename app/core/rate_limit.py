import logging
import time
from collections.abc import Awaitable, Callable
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.logging import log_event

TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local time = redis.call('TIME')
local now = tonumber(time[1]) + tonumber(time[2]) / 1000000
local bucket = redis.call('HMGET', key, 'tokens', 'timestamp')
local tokens = tonumber(bucket[1]) or capacity
local last = tonumber(bucket[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - last) * rate)
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end
redis.call('HSET', key, 'tokens', tokens, 'timestamp', now)
redis.call('EXPIRE', key, 300)
return allowed
"""

REDIS_CONNECTION_LOST: str = "REDIS_CONNECTION_LOST"
REDIS_UNAVAILABLE: str = "REDIS_CONNECTION_LOST"
LIMIT = "8"


class RedisUnavailable(Exception):
    pass


class TokenBucketLimiter:
    def __init__(
        self, redis: Redis, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.settings = get_settings()
        self.redis = redis
        self.clock = clock
        self.first_failure_at: float | None = None

    async def allowed(self, client_ip: str) -> bool:
        try:
            allowed = await cast(
                Awaitable[int],
                self.redis.eval(
                    TOKEN_BUCKET_LUA, 1, f"limit:ip:{client_ip}", 
                    self.settings.redis_bucket_limit_size, 
                    str(self.settings.redis_bucket_speed_size / 60)
                ),
            )
        except (RedisError, OSError, TimeoutError) as exc:
            now = self.clock()
            if self.first_failure_at is None:
                self.first_failure_at = now
                log_event(
                    logging.ERROR, REDIS_CONNECTION_LOST, reason=REDIS_UNAVAILABLE
                )
            if now - self.first_failure_at >= 120:
                raise RedisUnavailable from exc
            return True
        if self.first_failure_at is not None:
            log_event(logging.INFO, "REDIS_CONNECTION_RESTORED")
        self.first_failure_at = None
        return int(allowed) == 1
