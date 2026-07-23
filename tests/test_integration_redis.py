"""
D1/D2 Redis Runtime State Integration Tests

Tests the real combined path:
Redis → ProductionRedisClient → set_redis_client() → check_runtime_status()

These tests require:
- Redis running (docker compose up redis)
"""

import os
import pytest
from dotenv import load_dotenv

# Load environment before importing modules that depend on it
load_dotenv()

from services.runtime_state import check_runtime_status, set_redis_client, reset_redis_client, RuntimeStatus
from services.redis_client import ProductionRedisClient


# Test agent ID
TEST_AGENT_ID = "c90566c8-6300-4a69-8fef-56688c4a4e38"


@pytest.fixture(autouse=True)
def setup_redis():
    """Set up Redis client for all tests."""
    reset_redis_client()

    # Create real Redis client from environment
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        client = ProductionRedisClient(redis_url)
        set_redis_client(client)

    yield

    # Clean up Redis keys after tests
    try:
        client = ProductionRedisClient(redis_url)
        client.client.delete("fleet:halted")
        client.client.delete(f"agent:{TEST_AGENT_ID}:status")
    except Exception:
        pass  # Redis might not be available

    reset_redis_client()


class TestRedisRuntimeStateIntegration:
    """Integration tests for real Redis + D2's check_runtime_status()."""

    def test_missing_keys_operational_defaults(self):
        """Test that missing keys result in operational defaults (all False)."""
        # Ensure keys don't exist
        client = ProductionRedisClient(os.environ["REDIS_URL"])
        client.client.delete("fleet:halted")
        client.client.delete(f"agent:{TEST_AGENT_ID}:status")

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is True, "Missing keys should be available"
        assert status.fleet_halted is False, "Missing fleet:halted should default to False"
        assert status.agent_revoked is False, "Missing agent status should default to False"

    def test_active_agent_operational_fleet(self):
        """Test active agent with operational fleet."""
        client = ProductionRedisClient(os.environ["REDIS_URL"])
        client.client.set("fleet:halted", "false")
        client.client.set(f"agent:{TEST_AGENT_ID}:status", "active")

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is True
        assert status.fleet_halted is False
        assert status.agent_revoked is False

    def test_fleet_halted(self):
        """Test fleet halted state."""
        client = ProductionRedisClient(os.environ["REDIS_URL"])
        client.client.set("fleet:halted", "true")
        client.client.set(f"agent:{TEST_AGENT_ID}:status", "active")

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is True
        assert status.fleet_halted is True, "fleet:halted=true should set fleet_halted=True"
        assert status.agent_revoked is False

    def test_agent_revoked(self):
        """Test agent revoked state."""
        client = ProductionRedisClient(os.environ["REDIS_URL"])
        client.client.set("fleet:halted", "false")
        client.client.set(f"agent:{TEST_AGENT_ID}:status", "revoked")

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is True
        assert status.fleet_halted is False
        assert status.agent_revoked is True, "status=revoked should set agent_revoked=True"

    def test_revoked_and_fleet_halted(self):
        """Test both revoked and fleet halted."""
        client = ProductionRedisClient(os.environ["REDIS_URL"])
        client.client.set("fleet:halted", "true")
        client.client.set(f"agent:{TEST_AGENT_ID}:status", "revoked")

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is True
        assert status.fleet_halted is True, "Both states should be represented"
        assert status.agent_revoked is True, "Both states should be represented"

    def test_malformed_redis_value_fails_closed(self):
        """Test that malformed Redis values result in available=False."""
        client = ProductionRedisClient(os.environ["REDIS_URL"])
        client.client.set("fleet:halted", "invalid-value")
        client.client.set(f"agent:{TEST_AGENT_ID}:status", "active")

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is False, "Malformed value should result in unavailable"

    def test_bytes_vs_str_redis_values(self):
        """Test that both bytes and str values work correctly."""
        client = ProductionRedisClient(os.environ["REDIS_URL"])

        # Test with str value (Redis default)
        client.client.set("fleet:halted", "true")
        status = check_runtime_status(TEST_AGENT_ID)
        assert status.fleet_halted is True

        # Test with bytes value
        client.client.set("fleet:halted", b"true")
        status = check_runtime_status(TEST_AGENT_ID)
        assert status.fleet_halted is True


class TestRedisFailClosed:
    """Tests for fail-closed behavior with Redis failures."""

    def test_redis_unavailable_fails_closed(self):
        """Test that Redis being unavailable results in available=False."""
        # Create a client with invalid URL to simulate Redis failure
        try:
            bad_client = ProductionRedisClient("redis://invalid-host:9999/0")
            reset_redis_client()
            set_redis_client(bad_client)

            status = check_runtime_status(TEST_AGENT_ID)

            # Should be unavailable (not crash)
            assert status.available is False, "Redis failure should result in available=False"
            assert status.fleet_halted is False
            assert status.agent_revoked is False

        finally:
            # Restore working client
            reset_redis_client()
            client = ProductionRedisClient(os.environ["REDIS_URL"])
            set_redis_client(client)

    def test_redis_not_configured_fails_closed(self):
        """Test that no Redis client configured results in available=False."""
        reset_redis_client()

        status = check_runtime_status(TEST_AGENT_ID)

        assert status.available is False, "No Redis client should result in available=False"
