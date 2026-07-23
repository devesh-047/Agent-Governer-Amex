"""
Startup Wiring Tests

Tests that the bootstrap correctly wires D1 and D2 dependencies.
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()


class TestStartupWiring:
    """Tests that main.py bootstrap wires dependencies correctly."""

    def test_set_agent_lookup_receives_working_implementation(self):
        """Verify set_agent_lookup() receives working D1AgentLookup."""
        from services.identity import set_agent_lookup, reset_agent_lookup, verify_identity
        from scripts.agent_lookup import D1AgentLookup

        reset_agent_lookup()

        # Wire D1AgentLookup
        set_agent_lookup(D1AgentLookup())

        # Test that it works with a real agent
        result = verify_identity("c90566c8-6300-4a69-8fef-56688c4a4e38", "test-secret-123")

        assert result.valid is True, "Wired lookup should work with real agent"

    def test_set_redis_client_receives_working_implementation(self):
        """Verify set_redis_client() receives working ProductionRedisClient."""
        from services.runtime_state import set_redis_client, reset_redis_client, check_runtime_status
        from services.redis_client import ProductionRedisClient

        reset_redis_client()

        # Wire ProductionRedisClient
        redis_url = os.environ.get("REDIS_URL")
        assert redis_url, "REDIS_URL must be set"

        client = ProductionRedisClient(redis_url)
        set_redis_client(client)

        # Test that it works
        status = check_runtime_status("any-agent-id")

        assert status.available is True, "Wired Redis client should work"


class TestBootstrapFunction:
    """Tests for main.py's bootstrap_dependencies() function."""

    def test_bootstrap_wires_both_dependencies(self):
        """Test that bootstrap_dependencies() wires both adapters."""
        from main import bootstrap_dependencies
        from services.identity import reset_agent_lookup, verify_identity
        from services.runtime_state import reset_redis_client, check_runtime_status

        # Reset to clean state
        reset_agent_lookup()
        reset_redis_client()

        # Run bootstrap
        bootstrap_dependencies()

        # Verify both services work
        identity_result = verify_identity("c90566c8-6300-4a69-8fef-56688c4a4e38", "test-secret-123")
        assert identity_result.valid is True, "Identity should work after bootstrap"

        runtime_status = check_runtime_status("c90566c8-6300-4a69-8fef-56688c4a4e38")
        assert runtime_status.available is True, "Runtime check should work after bootstrap"
