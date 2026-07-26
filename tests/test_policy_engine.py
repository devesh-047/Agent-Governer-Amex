"""Tests for policy evaluation (Milestone 2)."""

import pytest

from policy.fallback import evaluate_policy_python
from policy.opa_client import evaluate_policy

def test_python_fallback_allowed():
    """Test Python fallback logic for allowed action."""
    result = evaluate_policy_python(
        permissions=["refund", "credit"],
        max_single_amount=500.0,
        action_type="refund",
        amount=250.0
    )
    assert result.allowed is True
    assert result.reason_code == "OK"
    assert result.policy_version == "fallback-1.0"

def test_python_fallback_unauthorized_action():
    """Test Python fallback logic for unauthorized action."""
    result = evaluate_policy_python(
        permissions=["credit"],
        max_single_amount=500.0,
        action_type="refund",
        amount=250.0
    )
    assert result.allowed is False
    assert result.reason_code == "PERMISSION_DENIED"
    assert result.policy_version == "fallback-1.0"

def test_python_fallback_amount_exceeds_limit():
    """Test Python fallback logic for amount exceeding limit."""
    result = evaluate_policy_python(
        permissions=["refund", "credit"],
        max_single_amount=500.0,
        action_type="refund",
        amount=600.0
    )
    assert result.allowed is False
    assert result.reason_code == "AMOUNT_EXCEEDS_LIMIT"
    assert result.policy_version == "fallback-1.0"

def test_opa_client_fallback_when_unreachable():
    """Test that OPA client transparently falls back when OPA is unreachable."""
    # By default, OPA is not running on localhost:8181 during tests.
    # The client should catch the connection error and use the fallback.
    result = evaluate_policy(
        permissions=["refund"],
        max_single_amount=100.0,
        action_type="refund",
        amount=50.0
    )
    assert result.allowed is True
    assert result.reason_code == "OK"
    assert result.policy_version == "fallback-1.0"
    
    # Test deny fallback
    result_deny = evaluate_policy(
        permissions=["refund"],
        max_single_amount=100.0,
        action_type="invalid_action",
        amount=50.0
    )
    assert result_deny.allowed is False
    assert result_deny.reason_code == "PERMISSION_DENIED"
    assert result_deny.policy_version == "fallback-1.0"
