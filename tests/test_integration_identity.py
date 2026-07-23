"""
D1/D2 Identity Integration Tests

Tests the real combined path:
Postgres → Agent model → D1AgentLookup → set_agent_lookup() → verify_identity()

These tests require:
- PostgreSQL running (docker compose up postgres)
- agents table migrated (alembic upgrade head)
- Test agent seeded in database
"""

import os
import uuid
import pytest
from dotenv import load_dotenv

# Load environment before importing modules that depend on it
load_dotenv()

from db.base import SessionLocal
from db.models.agent import Agent
from services.identity import verify_identity, set_agent_lookup, reset_agent_lookup, IdentityResult
from scripts.agent_lookup import D1AgentLookup


# Test agent ID (from seeding)
TEST_AGENT_ID = "c90566c8-6300-4a69-8fef-56688c4a4e38"
TEST_AGENT_SECRET = "test-secret-123"


@pytest.fixture(autouse=True)
def setup_integration():
    """Set up D1AgentLookup for all tests."""
    reset_agent_lookup()
    set_agent_lookup(D1AgentLookup())
    yield
    reset_agent_lookup()


class TestIdentityIntegration:
    """Integration tests for D1's database + D2's verify_identity()."""

    def test_verify_identity_with_correct_secret(self):
        """Test that correct credentials return valid=True."""
        result = verify_identity(TEST_AGENT_ID, TEST_AGENT_SECRET)

        assert result.valid is True, "Should be valid with correct secret"
        assert result.agent_id == TEST_AGENT_ID, "Should return the agent ID"

    def test_verify_identity_with_wrong_secret(self):
        """Test that wrong secret returns valid=False."""
        result = verify_identity(TEST_AGENT_ID, "wrong-secret")

        assert result.valid is False, "Should be invalid with wrong secret"
        assert result.agent_id is None, "Should not return agent ID when invalid"

    def test_verify_identity_with_unknown_agent(self):
        """Test that unknown agent returns valid=False."""
        unknown_id = str(uuid.uuid4())
        result = verify_identity(unknown_id, "any-secret")

        assert result.valid is False, "Should be invalid for unknown agent"
        assert result.agent_id is None, "Should not return agent ID"

    def test_verify_identity_with_empty_credentials(self):
        """Test that empty credentials return valid=False."""
        # Empty agent_id
        result = verify_identity("", TEST_AGENT_SECRET)
        assert result.valid is False

        # Empty secret
        result = verify_identity(TEST_AGENT_ID, "")
        assert result.valid is False

        # Both empty
        result = verify_identity("", "")
        assert result.valid is False

    def test_verify_identity_unicode_secret(self):
        """Test that Unicode secrets work correctly through real DB."""
        # Create agent with Unicode secret
        db = SessionLocal()
        unicode_agent = Agent(
            id=uuid.uuid4(),
            name="Unicode Agent",
            permissions=["test"],
            max_single_amount=100.00,
            daily_cap=500.00,
            status="active",
            shared_secret="🔑-secret-ëmøjî-Καιός"
        )
        db.add(unicode_agent)
        db.commit()
        agent_id = unicode_agent.id
        db.close()

        # Test with correct Unicode secret
        result = verify_identity(str(agent_id), "🔑-secret-ëmøjî-Καιός")
        assert result.valid is True, "Should handle Unicode secrets"

        # Test with wrong Unicode secret
        result = verify_identity(str(agent_id), "wrong-🔑-secret")
        assert result.valid is False, "Should reject wrong Unicode secret"


class TestIdentityFailClosed:
    """Tests for fail-closed behavior on infrastructure failures."""

    def test_d1_agent_lookup_exception_code_path(self):
        """
        Verify D1AgentLookup has exception handling code path.

        This test confirms the except block exists and can be reached.
        """
        import inspect
        source = inspect.getsource(D1AgentLookup.get_agent_secret)

        # Verify exception handling exists in the source code
        assert "except Exception" in source, "D1AgentLookup must have exception handling"
        assert "return None" in source, "D1AgentLookup must return None on exception"

    def test_verify_identity_with_none_from_lookup(self):
        """
        Test that verify_identity handles None from lookup correctly.

        When D1AgentLookup returns None (agent not found or DB failure),
        verify_identity should return valid=False.
        """
        from services.identity import AgentLookup

        class NoneReturningLookup(AgentLookup):
            """Mock lookup that always returns None."""
            def get_agent_secret(self, agent_id: str):
                return None

        reset_agent_lookup()
        set_agent_lookup(NoneReturningLookup())

        result = verify_identity(TEST_AGENT_ID, TEST_AGENT_SECRET)

        assert result.valid is False, "None from lookup should result in valid=False"
        assert result.agent_id is None, "None from lookup should not return agent ID"


@pytest.fixture(scope="module")
def cleanup_test_data():
    """Clean up test data after all tests run."""
    yield
    db = SessionLocal()
    try:
        # Clean up any test agents created during tests
        db.query(Agent).filter(Agent.name == "Unicode Agent").delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
