from types import SimpleNamespace
from typing import cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from app.core.rate_limit import RedisUnavailable, TokenBucketLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.fail = False
        self.count = 0

    async def eval(self, *args: object) -> int:
        if self.fail:
            raise ConnectionError("Connection failed")
        self.count += 1
        return 1 if self.count <= 8 else 0


@pytest.mark.asyncio
async def test_bucket_and_redis_outage_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(
            redis_bucket_limit_size=8,
            redis_bucket_speed_size=5,
        ),
    )

    client = FakeRedis()
    now = [0.0]
    limiter = TokenBucketLimiter(cast(Redis, client), clock=lambda: now[0])

    assert all([await limiter.allowed("192.168.0.1") for _ in range(8)])
    assert not await limiter.allowed("192.168.0.1")

    client.fail = True
    assert await limiter.allowed("192.168.0.1")

    now[0] = 119.9
    assert await limiter.allowed("192.168.0.1")

    now[0] = 120.0
    with pytest.raises(RedisUnavailable):
        await limiter.allowed("192.168.0.1")

    client.fail = False
    assert not await limiter.allowed("192.168.0.1")
    assert limiter.first_failure_at is None
    