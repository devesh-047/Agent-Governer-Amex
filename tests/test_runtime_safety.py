"""
Unit Tests for Runtime State Safety (D2.2)

Tests cover all safety-critical behaviors:
- Valid operational states (all keys missing, fleet halted, agent revoked)
- Redis unreachable/unconfigured scenarios
- Parse failures (decode errors, unrecognized values, unexpected types)
- Data type variations (bytes, str, None)
- Edge cases (empty agent_id, concurrent reads)

Comprehensive coverage of 20+ scenarios from the approved design.

所有权: D2 - test_runtime_safety.py
依赖: services/runtime_state.py
"""

import pytest
from services.runtime_state import (
    check_runtime_status,
    RuntimeStatus,
    RedisClient,
    set_redis_client,
    reset_redis_client,
    _parse_redis_value,
)
from typing import Optional, Union


class FakeRedis(RedisClient):
    """
    Fake Redis client for testing.

    Fake Redis exists ONLY in tests, never in production code.
    This simulates the Redis GET operations needed for D2.2.
    """

    def __init__(self, store: dict[str, Optional[Union[str, bytes]]]):
        """
        Initialize with a mapping of key -> value.

        Args:
            store: Dictionary of test Redis state
        """
        self._store = store.copy()

    def get(self, key: str) -> Optional[Union[str, bytes]]:
        """Retrieve a value from the fake Redis."""
        return self._store.get(key)

    def set(self, key: str, value: Optional[Union[str, bytes]]) -> None:
        """
        Set a value in the fake Redis (for test setup).

        Args:
            key: The Redis key
            value: The value to set (or None to delete)
        """
        if value is None:
            self._store.pop(key, None)
        else:
            self._store[key] = value


@pytest.fixture(autouse=True)
def reset_redis_between_tests():
    """Reset the Redis client before and after each test."""
    reset_redis_client()
    yield
    reset_redis_client()


class TestParseRedisValue:
    """Tests for the _parse_redis_value helper function."""

    def test_parse_canonical_true_bytes(self):
        """Canonical 'true' as bytes should parse to True."""
        assert _parse_redis_value(b"true", "true", "false") is True

    def test_parse_canonical_true_str(self):
        """Canonical 'true' as str should parse to True."""
        assert _parse_redis_value("true", "true", "false") is True

    def test_parse_canonical_false_bytes(self):
        """Canonical 'false' as bytes should parse to False."""
        assert _parse_redis_value(b"false", "true", "false") is False

    def test_parse_canonical_false_str(self):
        """Canonical 'false' as str should parse to False."""
        assert _parse_redis_value("false", "true", "false") is False

    def test_parse_none_returns_none(self):
        """None (missing key) should return None (operational default)."""
        assert _parse_redis_value(None, "true", "false") is None

    def test_parse_unrecognized_value_returns_none(self):
        """Unrecognized value should return None (fail-closed)."""
        assert _parse_redis_value(b"unknown", "true", "false") is None

    def test_decode_error_returns_none(self):
        """Bytes that fail UTF-8 decode should return None (fail-closed)."""
        # Invalid UTF-8 sequence
        invalid_bytes = b'\xff\xfe'
        assert _parse_redis_value(invalid_bytes, "true", "false") is None

    def test_parse_with_custom_canonical_values(self):
        """Should work with custom canonical value pairs."""
        assert _parse_redis_value(b"active", "active", "revoked") is True
        assert _parse_redis_value("revoked", "active", "revoked") is False


class TestOperationalDefaults:
    """Tests for overlay model - missing keys → operational defaults."""

    def test_both_keys_missing_returns_operational(self):
        """Missing both keys → fleet_halted=False, agent_revoked=False, available=True."""
        redis = FakeRedis({})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is False
        assert status.agent_revoked is False
        assert status.available is True

    def test_only_fleet_key_missing(self):
        """Missing fleet:halted → fleet_halted=False (operational default)."""
        redis = FakeRedis({"agent:agent_123:status": b"revoked"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is False
        assert status.agent_revoked is True
        assert status.available is True

    def test_only_agent_key_missing(self):
        """Missing agent:{id}:status → agent_revoked=False (operational default)."""
        redis = FakeRedis({"fleet:halted": b"true"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is True
        assert status.agent_revoked is False
        assert status.available is True

    def test_all_keys_present_operational(self):
        """All keys present with operational values."""
        redis = FakeRedis({
            "fleet:halted": b"false",
            "agent:agent_123:status": b"active"
        })
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is False
        assert status.agent_revoked is False
        assert status.available is True


class TestFleetHalted:
    """Tests for fleet:halted key behavior."""

    def test_fleet_halted_true_bytes(self):
        """fleet:halted="true" (bytes) → fleet_halted=True."""
        redis = FakeRedis({"fleet:halted": b"true"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is True
        assert status.available is True

    def test_fleet_halted_true_str(self):
        """fleet:halted="true" (str) → fleet_halted=True."""
        redis = FakeRedis({"fleet:halted": "true"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is True
        assert status.available is True

    def test_fleet_halted_false_bytes(self):
        """fleet:halted="false" (bytes) → fleet_halted=False."""
        redis = FakeRedis({"fleet:halted": b"false"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is False
        assert status.available is True

    def test_fleet_halted_false_str(self):
        """fleet:halted="false" (str) → fleet_halted=False."""
        redis = FakeRedis({"fleet:halted": "false"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.fleet_halted is False
        assert status.available is True


class TestAgentRevoked:
    """Tests for agent:{id}:status key behavior."""

    def test_agent_revoked_bytes(self):
        """agent:{id}:status="revoked" (bytes) → agent_revoked=True."""
        redis = FakeRedis({"agent:agent_123:status": b"revoked"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.agent_revoked is True
        assert status.available is True

    def test_agent_revoked_str(self):
        """agent:{id}:status="revoked" (str) → agent_revoked=True."""
        redis = FakeRedis({"agent:agent_123:status": "revoked"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.agent_revoked is True
        assert status.available is True

    def test_agent_active_bytes(self):
        """agent:{id}:status="active" (bytes) → agent_revoked=False."""
        redis = FakeRedis({"agent:agent_123:status": b"active"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.agent_revoked is False
        assert status.available is True

    def test_agent_active_str(self):
        """agent:{id}:status="active" (str) → agent_revoked=False."""
        redis = FakeRedis({"agent:agent_123:status": "active"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.agent_revoked is False
        assert status.available is True


class TestFailClosedBehavior:
    """Tests for fail-closed behavior on errors/malformed values."""

    def test_redis_not_configured(self):
        """No Redis client configured → available=False (fail-closed)."""
        # Don't call set_redis_client
        reset_redis_client()
        status = check_runtime_status("agent_123")

        assert status.available is False
        assert status.fleet_halted is False
        assert status.agent_revoked is False

    def test_redis_connection_error(self):
        """Redis throws exception → available=False (fail-closed)."""
        class ErrorRedis(RedisClient):
            def get(self, key: str) -> Optional[Union[str, bytes]]:
                raise ConnectionError("Redis unreachable")

        set_redis_client(ErrorRedis())
        status = check_runtime_status("agent_123")

        assert status.available is False
        assert status.fleet_halted is False
        assert status.agent_revoked is False

    def test_fleet_key_malformed_unrecognized(self):
        """fleet:halted has unrecognized value → available=False."""
        redis = FakeRedis({"fleet:halted": b"unknown"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_agent_key_malformed_unrecognized(self):
        """agent:{id}:status has unrecognized value → available=False."""
        redis = FakeRedis({"agent:agent_123:status": b"suspended"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_fleet_key_decode_error(self):
        """fleet:halted has invalid UTF-8 bytes → available=False."""
        redis = FakeRedis({"fleet:halted": b'\xff\xfe'})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_agent_key_decode_error(self):
        """agent:{id}:status has invalid UTF-8 bytes → available=False."""
        redis = FakeRedis({"agent:agent_123:status": b'\xff\xfe'})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_fleet_key_unexpected_type(self):
        """fleet:halted has unexpected type → available=False."""
        class WeirdRedis(RedisClient):
            def get(self, key: str):
                return 123  # Not str or bytes

        set_redis_client(WeirdRedis())
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_agent_key_unexpected_type(self):
        """agent:{id}:status has unexpected type → available=False."""
        class WeirdRedis(RedisClient):
            def get(self, key: str):
                if key.startswith("agent:"):
                    return ["list"]  # Not str or bytes
                return None

        set_redis_client(WeirdRedis())
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_empty_agent_id(self):
        """Empty agent_id → available=False (fail-closed)."""
        redis = FakeRedis({})
        set_redis_client(redis)
        status = check_runtime_status("")

        assert status.available is False

    def test_none_agent_id(self):
        """None agent_id → available=False (fail-closed)."""
        redis = FakeRedis({})
        set_redis_client(redis)
        status = check_runtime_status(None)

        assert status.available is False


class TestCanonicalOnlyValues:
    """Tests that only canonical values are accepted (no 1/0, case-sensitive)."""

    def test_fleet_halted_rejects_numeric_1(self):
        """fleet:halted="1" should NOT be accepted as true."""
        redis = FakeRedis({"fleet:halted": b"1"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_fleet_halted_rejects_numeric_0(self):
        """fleet:halted="0" should NOT be accepted as false."""
        redis = FakeRedis({"fleet:halted": b"0"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_fleet_halted_case_sensitive_true(self):
        """fleet:halted="True" should NOT be accepted."""
        redis = FakeRedis({"fleet:halted": b"True"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_agent_status_case_sensitive_revoked(self):
        """agent:{id}:status="Revoked" should NOT be accepted."""
        redis = FakeRedis({"agent:agent_123:status": b"Revoked"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False

    def test_agent_status_rejects_numeric(self):
        """agent:{id}:status="1" should NOT be accepted."""
        redis = FakeRedis({"agent:agent_123:status": b"1"})
        set_redis_client(redis)
        status = check_runtime_status("agent_123")

        assert status.available is False


class TestMultipleAgents:
    """Tests for checking multiple agents with different states."""

    def test_different_agents_independent_status(self):
        """Each agent has independent revocation status."""
        redis = FakeRedis({
            "agent:agent_a:status": b"revoked",
            "agent:agent_b:status": b"active",
            "agent:agent_c:status": b"revoked",
        })
        set_redis_client(redis)

        status_a = check_runtime_status("agent_a")
        status_b = check_runtime_status("agent_b")
        status_c = check_runtime_status("agent_c")

        assert status_a.agent_revoked is True
        assert status_b.agent_revoked is False
        assert status_c.agent_revoked is True

    def test_fleet_halted_affects_all_agents(self):
        """Fleet halted state should apply to all agents."""
        redis = FakeRedis({
            "fleet:halted": b"true",
            "agent:agent_a:status": b"active",
            "agent:agent_b:status": b"active",
        })
        set_redis_client(redis)

        status_a = check_runtime_status("agent_a")
        status_b = check_runtime_status("agent_b")

        assert status_a.fleet_halted is True
        assert status_b.fleet_halted is True


class TestRuntimeStatusFrozen:
    """Tests for RuntimeStatus immutability."""

    def test_runtime_status_is_frozen_dataclass(self):
        """RuntimeStatus should be a frozen dataclass."""
        status = RuntimeStatus(
            fleet_halted=False,
            agent_revoked=False,
            available=True
        )

        # Should be immutable
        with pytest.raises(AttributeError):
            status.fleet_halted = True

        with pytest.raises(AttributeError):
            status.agent_revoked = True

        with pytest.raises(AttributeError):
            status.available = False

    def test_runtime_status_all_required_fields(self):
        """RuntimeStatus requires all three fields."""
        status = RuntimeStatus(
            fleet_halted=True,
            agent_revoked=True,
            available=False
        )

        assert status.fleet_halted is True
        assert status.agent_revoked is True
        assert status.available is False


class TestModuleLevelDependencyInjection:
    """Tests for module-level dependency injection pattern."""

    def test_set_redis_client_configures_module(self):
        """set_redis_client should configure the module-level client."""
        redis = FakeRedis({"fleet:halted": b"true"})
        set_redis_client(redis)

        status = check_runtime_status("agent_123")
        assert status.fleet_halted is True

    def test_reset_redis_client_clears_configuration(self):
        """reset_redis_client should clear the configured client."""
        redis = FakeRedis({"fleet:halted": b"true"})
        set_redis_client(redis)
        reset_redis_client()

        status = check_runtime_status("agent_123")
        assert status.available is False  # Fails closed when no client

    def test_set_redis_client_can_be_replaced(self):
        """set_redis_client should allow replacing the client."""
        redis1 = FakeRedis({"fleet:halted": b"true"})
        redis2 = FakeRedis({"fleet:halted": b"false"})

        set_redis_client(redis1)
        status1 = check_runtime_status("agent_123")
        assert status1.fleet_halted is True

        set_redis_client(redis2)
        status2 = check_runtime_status("agent_123")
        assert status2.fleet_halted is False


class TestFrozenContractSignature:
    """Verify the frozen contract is preserved."""

    def test_check_runtime_status_one_parameter_signature(self):
        """
        check_runtime_status must have exactly one parameter: agent_id.

        This is the frozen contract specified in tasks-detailed.md.
        Any change to this signature is a breaking change.
        """
        import inspect

        sig = inspect.signature(check_runtime_status)
        params = list(sig.parameters.keys())

        # Must be exactly ['agent_id']
        assert params == ['agent_id'], f"Signature changed to {params}"
        assert len(params) == 1, f"Expected 1 parameter, got {len(params)}"

    def test_return_type_is_runtime_status(self):
        """check_runtime_status must return RuntimeStatus."""
        redis = FakeRedis({})
        set_redis_client(redis)

        status = check_runtime_status("agent_123")

        # Should be RuntimeStatus type
        assert isinstance(status, RuntimeStatus)
        assert hasattr(status, 'fleet_halted')
        assert hasattr(status, 'agent_revoked')
        assert hasattr(status, 'available')


class TestFakeRedisInTestsOnly:
    """Verify fake Redis exists only in test code."""

    def test_fake_redis_class_exists_only_in_tests(self):
        """
        The FakeRedis class should exist only in this test file.
        Production code should NOT contain any fake/hard-coded Redis.

        This test documents that all fake Redis implementations are test-only.
        """
        # All fake Redis in this file are defined only within test methods
        # No hard-coded Redis connections exist in services/runtime_state.py
        import services.runtime_state as runtime_module

        # Verify no fake Redis in production module
        assert not hasattr(runtime_module, 'FakeRedis')
        assert not hasattr(runtime_module, 'TEST_REDIS')
        assert not hasattr(runtime_module, 'MOCK_REDIS')


class TestConcurrentSafety:
    """Tests for concurrent read safety (D2.2 is read-only)."""

    def test_concurrent_reads_are_safe(self):
        """
        Multiple concurrent reads should be safe.

        D2.2 only reads from Redis, so concurrent reads are inherently safe.
        Writes (revoke/restore/halt/resume) are D2.3/D2.4's responsibility.
        """
        import threading

        redis = FakeRedis({
            "fleet:halted": b"true",
            "agent:agent_123:status": b"revoked"
        })
        set_redis_client(redis)

        results = []
        errors = []

        def read_status():
            try:
                status = check_runtime_status("agent_123")
                results.append(status)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_status) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent reads: {errors}"
        assert len(results) == 10

        # All results should be consistent
        for status in results:
            assert status.fleet_halted is True
            assert status.agent_revoked is True
            assert status.available is True
