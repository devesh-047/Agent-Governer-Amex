"""
Redis Client Adapter (D2.2 Integration)

Domain: D2 - Runtime Safety
Ownership: services/redis_client.py

This module provides a production RedisClient adapter for D2's check_runtime_status().
It wraps redis-py and implements the RedisClient protocol defined in runtime_state.py.

IMPORTANT: This adapter does NOT swallow Redis exceptions.
Exceptions must propagate to runtime_state.py for fail-closed behavior.

Integration:
- D1 creates this adapter with REDIS_URL from environment
- D1 calls set_redis_client() during application startup
- D2's check_runtime_status() uses the adapter via dependency injection

Redis Exception Handling:
- Connection errors → propagate to runtime_state.py → available=False
- Timeout errors → propagate to runtime_state.py → available=False
- This preserves fail-closed semantics
"""

import os
import logging
from typing import Optional, Union
import redis

logger = logging.getLogger(__name__)


class ProductionRedisClient:
    """
    Production Redis client adapter implementing D2's RedisClient protocol.

    This wraps redis-py to provide the get() method required by runtime_state.py.
    Redis exceptions are NOT caught - they propagate for fail-closed handling.
    """

    def __init__(self, redis_url: str):
        """
        Initialize Redis client.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        self.client = redis.from_url(redis_url, decode_responses=False)
        logger.info(f"Redis client initialized for: {redis_url}")

    def get(self, key: str) -> Optional[Union[str, bytes]]:
        """
        Retrieve a value from Redis by key.

        This method implements the RedisClient protocol. It returns the raw
        response from redis-py (str, bytes, or None) without transformation.

        IMPORTANT: Redis exceptions (connection errors, timeouts, etc.) are NOT
        caught here. They propagate to the caller (runtime_state.py) which
        converts them to fail-closed behavior (available=False).

        Args:
            key: The Redis key to retrieve

        Returns:
            - bytes: Raw bytes from Redis (typical for redis-py)
            - str: Decoded string (if decode_responses=True)
            - None: Key does not exist

        Raises:
            RedisError: Connection failures, timeouts, etc. (propagated)
        """
        # Direct delegation - no exception handling
        # runtime_state.py depends on exceptions propagating for fail-closed
        return self.client.get(key)

    def set(self, key: str, value: str, nx: bool = False) -> Optional[bool]:
        """Set a value in Redis.

        Args:
            key: The Redis key to set.
            value: The string value to store.
            nx: Only set if key does not already exist.

        Returns:
            True if set, False/None if nx=True and key already existed.

        Raises:
            RedisError: Connection failures, timeouts, etc. (propagated)
        """
        return self.client.set(key, value, nx=nx)

    def decrby(self, key: str, amount: int) -> int:
        """Atomically decrement a Redis integer key.

        Raises:
            RedisError: Connection failures, timeouts, etc. (propagated)
        """
        return self.client.decrby(key, amount)

    def incrby(self, key: str, amount: int) -> int:
        """Atomically increment a Redis integer key.

        Raises:
            RedisError: Connection failures, timeouts, etc. (propagated)
        """
        return self.client.incrby(key, amount)



def create_redis_client_from_env() -> ProductionRedisClient:
    """
    Create a ProductionRedisClient using REDIS_URL from environment.

    This is a convenience function for D1's startup code.

    Returns:
        ProductionRedisClient instance

    Raises:
        ValueError: If REDIS_URL is not set
    """
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable not set")

    return ProductionRedisClient(redis_url)
