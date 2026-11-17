from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core.rate_limit import TokenBucketLimiter


@pytest.mark.asyncio
async def test_atomic_redis_token_bucket(redis_client: Redis) -> None:
    test_client_id = f"test-{uuid4().hex}"
    limiter = TokenBucketLimiter(redis_client)
    for _ in range(8):
        assert await limiter.allowed(test_client_id)
    assert not await limiter.allowed(test_client_id)
