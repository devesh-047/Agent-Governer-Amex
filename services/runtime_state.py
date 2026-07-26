"""
Runtime State Service (D2.2)

Domain: D2 - Runtime Safety
Ownership: services/runtime_state.py

This module implements check_runtime_status(), which validates runtime safety
state using Redis-backed fleet and agent status tracking.

Safety Properties:
- Fail-closed: Redis unreachable → available=False
- Strict parsing: malformed/unrecognized values → available=False
- Overlay model: missing keys → operational defaults (fleet_halted=False, agent_revoked=False)
- Fail-closed handling for Redis errors and malformed runtime state

Integration (Module-Level Dependency Injection):
- RedisClient is a protocol representing Redis GET operations
- D1 calls set_redis_client() once during application initialization
- Tests call set_redis_client() with fake implementations
- This preserves the frozen check_runtime_status(agent_id) 1-parameter signature
- No fake production stubs or NotImplementedErrors

Redis Keys (D2-owned ONLY):
- fleet:halted - stores "true" or "false"
- agent:{id}:status - stores "active" or "revoked"

State Persistence:
NO TTLs on runtime safety keys. State changes occur ONLY through explicit
revoke/restore/halt/resume operations (D2.3, D2.4).
"""

import logging
from dataclasses import dataclass
from typing import Protocol, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)


class _Sentinel(Enum):
    """Sentinel value for Redis errors vs missing keys."""
    ERROR = 1


# Sentinel instance to distinguish Redis errors from missing keys
_REDIS_ERROR = _Sentinel.ERROR


@dataclass(frozen=True)
class RuntimeStatus:
    """
    Result of runtime status checking.

    Contract (frozen):
    - fleet_halted: bool - True if fleet-wide kill switch is active
    - agent_revoked: bool - True if this specific agent is revoked
    - available: bool - False if Redis unreachable or state is malformed

    This is a D2-defined schema. Do NOT duplicate in schemas/audit.py
    (that file is for genuinely D2-owned schemas required by tasks-detailed.md).

    Semantics:
    - Redis reachable + keys missing → fleet_halted=False, agent_revoked=False, available=True
    - fleet:halted="true" → fleet_halted=True
    - agent:{id}:status="revoked" → agent_revoked=True
    - Malformed/unrecognized/decode failure → available=False
    - Redis unavailable/timeout/error → available=False
    """
    fleet_halted: bool
    agent_revoked: bool
    available: bool


class RedisClient(Protocol):
    """
    Protocol for Redis GET and SET operations.

    This represents the Redis dependency. D1 will implement this interface
    to provide Redis access. Tests inject fake implementations.

    The protocol defines what D2 needs: GET for reads, SET for writes.
    """
    # Protocol for read operations (D2.2)
    def get(self, key: str) -> Optional[Union[str, bytes]]:
        """
        Retrieve a value from Redis by key.

        Args:
            key: The Redis key to retrieve

        Returns:
            The value if found, None otherwise. May return str or bytes.

        Note:
            Redis GET can return:
            - None: key does not exist
            - bytes: raw bytes from Redis (typical for redis-py)
            - str: decoded string (some client libraries)
            Implementations should return whatever the underlying Redis
            client returns without transformation.
        """
        ...

    # Protocol for write operations (D2.3/D2.4 + spend enforcement)
    def set(self, key: str, value: str, nx: bool = False) -> Optional[bool]:
        """Set a value in Redis.

        Args:
            key: The Redis key to set.
            value: The string value to store.
            nx: If True, only set when the key does not already exist
                (atomic initialisation for spend counters).

        Returns:
            True if the key was set, False/None if nx=True and key existed.

        Raises:
            RedisError: Connection failures, timeouts, etc. (should propagate).
        """
        ...

    def decrby(self, key: str, amount: int) -> int:
        """Atomically decrement an integer key by *amount*.

        Raises:
            RedisError: Connection failures, timeouts, etc. (should propagate).
        """
        ...

    def incrby(self, key: str, amount: int) -> int:
        """Atomically increment an integer key by *amount*.

        Raises:
            RedisError: Connection failures, timeouts, etc. (should propagate).
        """
        ...


# Module-level dependency injection
# Set by D1 during application initialization or by tests
_redis_client: Optional[RedisClient] = None


def set_redis_client(client: RedisClient) -> None:
    """
    Set the Redis client implementation.

    D1 MUST call this once during application initialization with a concrete
    implementation that connects to Redis. Tests call this with fake implementations.

    Args:
        client: An implementation of the RedisClient protocol

    Example (production, in D1's initialization):
    ```python
    from services.runtime_state import set_redis_client

    # D1 implements the protocol using their Redis architecture
    class MyRedisClient:
        def __init__(self, redis_url: str):
            import redis
            self.client = redis.from_url(redis_url)

        def get(self, key: str) -> Optional[Union[str, bytes]]:
            # Return the raw Redis response (str, bytes, or None)
            # Redis errors MUST propagate to _redis_get() for fail-closed handling
            return self.client.get(key)

    set_redis_client(MyRedisClient(redis_url))
    ```

    Example (test):
    ```python
    class FakeRedis:
        def __init__(self):
            self._store = {}

        def get(self, key: str):
            return self._store.get(key)

    set_redis_client(FakeRedis())
    ```
    """
    global _redis_client
    _redis_client = client


def reset_redis_client() -> None:
    """
    Reset the Redis client implementation.

    This is primarily used in tests to ensure clean state between test cases.
    Production code should never call this.

    Example (test teardown):
    ```python
    def teardown():
        reset_redis_client()
    ```
    """
    global _redis_client
    _redis_client = None


def get_redis_client() -> Optional[RedisClient]:
    """
    Get the configured Redis client implementation.

    Returns:
        The configured RedisClient or None if not set

    This allows Runtime Control APIs (D2.3/D2.4) to access the
    Redis client for write operations.
    """
    return _redis_client


def _parse_redis_value(
    value: Optional[Union[str, bytes]],
    canonical_true: str,
    canonical_false: str
) -> Optional[bool]:
    """
    Parse a Redis value into a boolean.

    Args:
        value: The raw value from Redis (None, str, or bytes)
        canonical_true: The canonical string representation of "true"
        canonical_false: The canonical string representation of "false"

    Returns:
        True if value matches canonical_true
        False if value matches canonical_false
        None if value is None (missing key)
        None if value is malformed/unrecognized (triggers fail-closed)

    Behavior:
        - None (missing key) → None → operational default
        - bytes matching canonical → corresponding bool
        - str matching canonical → corresponding bool
        - decode failure → None → fail-closed
        - unrecognized value → None → fail-closed

    Examples:
        _parse_redis_value(b"active", "active", "revoked") → True (bool)
        _parse_redis_value("revoked", "active", "revoked") → False (bool)
        _parse_redis_value(None, "active", "revoked") → None (missing)
        _parse_redis_value(b"unknown", "active", "revoked") → None (fail-closed)
    """
    # Missing key → None (operational default)
    if value is None:
        return None

    # Extract string value safely
    try:
        if isinstance(value, bytes):
            str_value = value.decode('utf-8')
        elif isinstance(value, str):
            str_value = value
        else:
            # Unrecognized type → fail-closed
            logger.debug(f"Unexpected Redis value type: {type(value)}")
            return None
    except (UnicodeDecodeError, AttributeError) as e:
        # Decode failure → fail-closed
        logger.debug(f"Failed to decode Redis value: {e}")
        return None

    # Match against canonical values
    if str_value == canonical_true:
        return True
    if str_value == canonical_false:
        return False

    # Unrecognized value → fail-closed
    logger.debug(f"Unrecognized Redis value: {str_value!r}")
    return None


def _redis_get(key: str) -> Union[Optional[Union[str, bytes]], _Sentinel]:
    """
    Internal helper to retrieve a value from Redis.

    This function encapsulates the dependency injection pattern and provides
    fail-closed error handling.

    Args:
        key: The Redis key to retrieve

    Returns:
        The raw value from Redis, None (missing key), or _REDIS_ERROR sentinel

    Note:
        - If no client is configured, returns _REDIS_ERROR sentinel
        - If Redis throws an exception, returns _REDIS_ERROR sentinel
        - This distinguishes "Redis error" from "key missing" (None)
    """
    if _redis_client is None:
        logger.warning("Redis client not configured - returning error sentinel")
        return _REDIS_ERROR

    try:
        return _redis_client.get(key)
    except Exception as e:
        # Any Redis error → fail-closed
        logger.warning(f"Redis GET error for key {key!r}: {e}")
        return _REDIS_ERROR


def check_runtime_status(agent_id: str) -> RuntimeStatus:
    """
    Check runtime safety status for an agent.

    This is the D2.2 implementation called by D1 during request processing.
    It validates both fleet-wide and per-agent runtime safety state.

    FROZEN CONTRACT - DO NOT CHANGE SIGNATURE:
    check_runtime_status(agent_id: str) -> RuntimeStatus

    Args:
        agent_id: The agent identifier to check

    Returns:
        RuntimeStatus indicating fleet state, agent revocation, and availability

    Behavior Matrix:
    +----------------+------------------+------------------+----------------+
    | Fleet Halted?  | Agent Revoked?   | Redis Reachable? | Return         |
    +----------------+------------------+------------------+----------------+
    | Yes/No/Missing | Yes/No/Missing   | Yes              | available=True |
    | Any            | Any              | No (error)       | available=False|
    | Any            | Any              | No (unconfigured)| available=False|
    +----------------+------------------+------------------+----------------+

    Missing keys are treated as operational defaults (overlay model):
    - Missing fleet:halted → fleet_halted=False (fleet is operational)
    - Missing agent:{id}:status → agent_revoked=False (agent is active)

    Redis Key/Value Contract:
    - fleet:halted stores "true" (halted) or "false" (operational)
    - agent:{id}:status stores "active" (operational) or "revoked" (blocked)
    - NO support for 1/0 or other boolean representations
    - NO support for case-insensitive matching

    Fail-Closed Behavior:
    Any of the following triggers available=False:
    - Redis client not configured
    - Redis connection error/timeout
    - Decode failure (bytes → UTF-8)
    - Unrecognized value in a key
    - Type error (unexpected type from Redis)

    Failure Modes:
    - Empty/None agent_id → available=False (fail-closed)
    - Redis unreachable → available=False (fail-closed)
    - Malformed value → available=False (fail-closed)
    - Unrecognized value → available=False (fail-closed)

    Example (D1's orchestration):
    ```python
    from services.runtime_state import check_runtime_status, set_redis_client

    # During app initialization (D1's responsibility)
    set_redis_client(your_redis_client_implementation)

    # In the request handler
    status = check_runtime_status(request.agent_id)
    if not status.available:
        return Response(status_code=503, reason="RUNTIME_STATE_UNAVAILABLE")
    if status.fleet_halted or status.agent_revoked:
        return Response(status_code=403, reason="RUNTIME_STATE_DENY")
    ```
    """
    # Guard against empty/None agent_id
    if not agent_id:
        logger.debug("Runtime status check failed: empty agent_id")
        return RuntimeStatus(
            fleet_halted=False,
            agent_revoked=False,
            available=False
        )

    # Read fleet:halted key
    fleet_value = _redis_get("fleet:halted")

    # Check for Redis error (unconfigured or connection error)
    if fleet_value is _REDIS_ERROR:
        logger.debug("Runtime status check failed: Redis error")
        return RuntimeStatus(
            fleet_halted=False,
            agent_revoked=False,
            available=False
        )

    fleet_halted = _parse_redis_value(
        fleet_value,
        canonical_true="true",
        canonical_false="false"
    )

    # Read agent:{id}:status key
    agent_key = f"agent:{agent_id}:status"
    agent_value = _redis_get(agent_key)

    # Check for Redis error (unconfigured or connection error)
    if agent_value is _REDIS_ERROR:
        logger.debug("Runtime status check failed: Redis error")
        return RuntimeStatus(
            fleet_halted=False,
            agent_revoked=False,
            available=False
        )

    agent_revoked = _parse_redis_value(
        agent_value,
        canonical_true="revoked",
        canonical_false="active"
    )

    # Determine if parsing succeeded (fail-closed check)
    # If either parse returned None due to malformed/unrecognized value,
    # we must mark unavailable
    if fleet_value is not None and fleet_halted is None:
        # fleet:halted exists but value is malformed/unrecognized
        logger.debug(f"Malformed fleet:halted value: {fleet_value!r}")
        return RuntimeStatus(
            fleet_halted=False,
            agent_revoked=False,
            available=False
        )

    if agent_value is not None and agent_revoked is None:
        # agent:{id}:status exists but value is malformed/unrecognized
        logger.debug(f"Malformed {agent_key} value: {agent_value!r}")
        return RuntimeStatus(
            fleet_halted=False,
            agent_revoked=False,
            available=False
        )

    # All parsing succeeded → operational
    # Missing keys → None → operational defaults (False for both)
    return RuntimeStatus(
        fleet_halted=fleet_halted or False,
        agent_revoked=agent_revoked or False,
        available=True
    )
