"""
Unit Tests for Identity Verification (D2.1)

Tests cover all security-critical behaviors:
- Valid credentials acceptance
- Invalid credentials rejection
- Unknown agent handling
- Empty/malformed input handling
- Timing-safe comparison correctness
- No agent_id exposure on failure

所有权: D2 - test_identity.py
依赖: services/identity.py
"""

import pytest
from services.identity import (
    verify_identity,
    IdentityResult,
    AgentLookup,
    set_agent_lookup,
    reset_agent_lookup,
)
from typing import Optional


class FakeAgentLookup(AgentLookup):
    """
    Fake agent lookup for testing.

    Fake agents exist ONLY in tests, never in production code.
    """

    def __init__(self, agents: dict[str, str]):
        """
        Initialize with a mapping of agent_id -> shared_secret.

        Args:
            agents: Dictionary of test agent credentials
        """
        self._agents = agents.copy()

    def get_agent_secret(self, agent_id: str) -> Optional[str]:
        """Retrieve the shared_secret for an agent."""
        return self._agents.get(agent_id)


@pytest.fixture(autouse=True)
def reset_lookup_between_tests():
    """Reset the agent lookup before and after each test."""
    reset_agent_lookup()
    yield
    reset_agent_lookup()


class TestIdentityVerificationValid:
    """Tests for valid identity verification."""

    def test_known_agent_with_correct_secret(self):
        """Known agent with correct secret should return valid=True with agent_id."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "secret_ABC")

        assert result.valid is True
        assert result.agent_id == "agent_123"

    def test_valid_result_contains_correct_agent_id(self):
        """Valid result should contain the correct agent_id."""
        lookup = FakeAgentLookup({"agent_xyz": "my_secret"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_xyz", "my_secret")

        assert result.valid is True
        assert result.agent_id == "agent_xyz"


class TestIdentityVerificationInvalid:
    """Tests for invalid identity verification."""

    def test_unknown_agent(self):
        """Unknown agent should return valid=False with agent_id=None."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("unknown_agent", "any_secret")

        assert result.valid is False
        assert result.agent_id is None

    def test_known_agent_with_wrong_secret(self):
        """Known agent with wrong secret should return valid=False."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "wrong_secret")

        assert result.valid is False
        assert result.agent_id is None

    def test_empty_secret(self):
        """Empty secret should fail safely."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "")

        assert result.valid is False
        assert result.agent_id is None

    def test_empty_agent_id(self):
        """Empty agent_id should fail safely."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("", "any_secret")

        assert result.valid is False
        assert result.agent_id is None

    def test_none_agent_id(self):
        """None agent_id should fail safely."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity(None, "any_secret")

        assert result.valid is False
        assert result.agent_id is None

    def test_none_secret(self):
        """None secret should fail safely."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", None)

        assert result.valid is False
        assert result.agent_id is None

    def test_no_lookup_configured(self):
        """When no lookup is configured, should fail closed."""
        # Don't call set_agent_lookup - test the unconfigured state
        reset_agent_lookup()
        result = verify_identity("any_agent", "any_secret")

        assert result.valid is False
        assert result.agent_id is None


class TestIdentityVerificationSecurity:
    """Tests for security properties."""

    def test_case_sensitive_secret_mismatch(self):
        """Secret comparison should be case-sensitive."""
        lookup = FakeAgentLookup({"agent_123": "Secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "secret_abc")

        assert result.valid is False
        assert result.agent_id is None

    def test_invalid_results_do_not_expose_agent_id(self):
        """Invalid results should never expose an agent_id."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)

        # Test various failure cases
        cases = [
            ("agent_123", "wrong_secret"),  # Wrong secret
            ("unknown", "any_secret"),       # Unknown agent
            ("agent_123", ""),               # Empty secret
            ("", "any_secret"),              # Empty agent_id
        ]

        for agent_id, secret in cases:
            result = verify_identity(agent_id, secret)
            assert result.valid is False, f"Failed for ({agent_id}, {secret})"
            assert result.agent_id is None, f"agent_id leaked for ({agent_id}, {secret})"

    def test_whitespace_in_secret_matters(self):
        """Secret comparison should consider whitespace significant."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "secret_ABC ")  # Trailing space

        assert result.valid is False
        assert result.agent_id is None


class TestIdentityVerificationIntegration:
    """Tests for D1 integration contract."""

    def test_multiple_agents_in_lookup(self):
        """Should correctly verify against multiple agents."""
        lookup = FakeAgentLookup({
            "agent_a": "secret_a",
            "agent_b": "secret_b",
            "agent_c": "secret_c",
        })
        set_agent_lookup(lookup)

        # Valid cases
        assert verify_identity("agent_a", "secret_a").valid is True
        assert verify_identity("agent_b", "secret_b").valid is True
        assert verify_identity("agent_c", "secret_c").valid is True

        # Invalid cases (cross-agent secrets)
        assert verify_identity("agent_a", "secret_b").valid is False
        assert verify_identity("agent_b", "secret_a").valid is False

    def test_lookup_returns_none_for_nonexistent_agent(self):
        """Should handle lookup returning None for non-existent agent."""
        class EmptyLookup(AgentLookup):
            def get_agent_secret(self, agent_id: str) -> Optional[str]:
                return None

        set_agent_lookup(EmptyLookup())
        result = verify_identity("any_agent", "any_secret")

        assert result.valid is False
        assert result.agent_id is None

    def test_special_characters_in_secret(self):
        """Should handle special characters in secrets correctly."""
        lookup = FakeAgentLookup({"agent_123": "p@ssw0rd!#$%"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "p@ssw0rd!#$%")

        assert result.valid is True
        assert result.agent_id == "agent_123"

    def test_unicode_characters_in_secret(self):
        """Should handle Unicode characters in secrets correctly."""
        lookup = FakeAgentLookup({"agent_123": "密码123🔒"})
        set_agent_lookup(lookup)
        result = verify_identity("agent_123", "密码123🔒")

        assert result.valid is True
        assert result.agent_id == "agent_123"


class TestIdentityResultFrozen:
    """Tests for IdentityResult immutability."""

    def test_identity_result_is_frozen_dataclass(self):
        """IdentityResult should be a frozen dataclass."""
        result = IdentityResult(valid=True, agent_id="agent_123")

        # Should be immutable
        with pytest.raises(AttributeError):
            result.valid = False

        with pytest.raises(AttributeError):
            result.agent_id = "other_agent"

    def test_identity_result_default_values(self):
        """IdentityResult should have correct default values."""
        result = IdentityResult(valid=False)

        assert result.valid is False
        assert result.agent_id is None


class TestFakeCredentialsInTestsOnly:
    """Verify fake credentials exist only in test code."""

    def test_fake_lookup_class_exists_only_in_tests(self):
        """
        The FakeAgentLookup class should exist only in this test file.
        Production code should NOT contain any fake/hard-coded credentials.

        This test documents that all fake agents are test-only.
        """
        # All fake agents in this file are defined only within test methods
        # No hard-coded credentials exist in services/identity.py
        import services.identity as identity_module

        # Verify no fake credentials in production module
        assert not hasattr(identity_module, 'FakeAgentLookup')
        assert not hasattr(identity_module, 'TEST_AGENTS')
        assert not hasattr(identity_module, 'MOCK_SECRET')


class TestModuleLevelDependencyInjection:
    """Tests for module-level dependency injection pattern."""

    def test_set_agent_lookup_configures_module(self):
        """set_agent_lookup should configure the module-level lookup."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)

        result = verify_identity("agent_123", "secret_ABC")
        assert result.valid is True

    def test_reset_agent_lookup_clears_configuration(self):
        """reset_agent_lookup should clear the configured lookup."""
        lookup = FakeAgentLookup({"agent_123": "secret_ABC"})
        set_agent_lookup(lookup)
        reset_agent_lookup()

        result = verify_identity("agent_123", "secret_ABC")
        assert result.valid is False  # Fails closed when no lookup

    def test_set_agent_lookup_can_be_replaced(self):
        """set_agent_lookup should allow replacing the lookup."""
        lookup1 = FakeAgentLookup({"agent_123": "secret_ABC"})
        lookup2 = FakeAgentLookup({"agent_456": "secret_XYZ"})

        set_agent_lookup(lookup1)
        result1 = verify_identity("agent_123", "secret_ABC")
        assert result1.valid is True
        assert verify_identity("agent_456", "secret_XYZ").valid is False

        set_agent_lookup(lookup2)
        result2 = verify_identity("agent_456", "secret_XYZ")
        assert result2.valid is True
        assert verify_identity("agent_123", "secret_ABC").valid is False


class TestFrozenContractSignature:
    """Verify the frozen contract is preserved."""

    def test_verify_identity_two_parameter_signature(self):
        """
        verify_identity must have exactly two parameters: agent_id and secret.

        This is the frozen contract specified in tasks-detailed.md.
        Any change to this signature is a breaking change.
        """
        import inspect

        sig = inspect.signature(verify_identity)
        params = list(sig.parameters.keys())

        # Must be exactly ['agent_id', 'secret']
        assert params == ['agent_id', 'secret'], f"Signature changed to {params}"
        assert len(params) == 2, f"Expected 2 parameters, got {len(params)}"

    def test_return_type_is_identity_result(self):
        """verify_identity must return IdentityResult."""
        result = verify_identity("test", "test")  # With no lookup, fails closed

        # Should be IdentityResult type
        assert isinstance(result, IdentityResult)
        assert hasattr(result, 'valid')
        assert hasattr(result, 'agent_id')
