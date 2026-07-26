"""Tests for spend cap enforcement and atomic budget reservation (Milestone 1)."""

import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor

from db.base import SessionLocal
from db.models.agent import Agent
from services.spend import (
    reserve_budget_atomic,
    reset_spend,
    get_remaining_budget,
    budget_rollback,
    SpendResult,
    REASON_OK,
    REASON_INSUFFICIENT,
    REASON_INVALID_AMOUNT,
    REASON_AGENT_NOT_FOUND,
)
from services.runtime_state import get_redis_client

from main import bootstrap_dependencies

@pytest.fixture(autouse=True)
def setup_redis_for_tests():
    """Ensure redis is configured before every test, since other tests clear it."""
    try:
        bootstrap_dependencies()
    except Exception:
        pass
    import os
    from services.redis_client import ProductionRedisClient
    from services.runtime_state import set_redis_client
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    set_redis_client(ProductionRedisClient(redis_url))

@pytest.fixture
def test_agent_id():
    """Create a temporary agent in the DB for testing."""
    agent_id = uuid.uuid4()
    with SessionLocal() as db:
        agent = Agent(
            id=agent_id,
            name="Spend Test Agent",
            permissions=["refund"],
            max_single_amount=500.0,
            daily_cap=1000.0,
            status="active",
            shared_secret="secret"
        )
        db.add(agent)
        db.commit()
    
    yield agent_id
    
    # We do NOT delete the agent from the DB during teardown, because if an audit log
    # was written for this agent, the foreign key constraint will block the delete,
    # and the audit_log table has append-only triggers preventing its deletion.
    # The test DB will just accumulate test agents.
    
    # Cleanup redis
    redis_client = get_redis_client()
    if redis_client:
        redis_client.client.delete(f"agent:{agent_id}:remaining_budget")

def test_initial_budget(test_agent_id):
    """Test that budget is correctly initialized from DB."""
    budget = get_remaining_budget(test_agent_id)
    assert budget == 1000.0

def test_reserve_budget_success(test_agent_id):
    """Test successful budget reservation."""
    result = reserve_budget_atomic(test_agent_id, 250.0)
    assert result.allowed is True
    assert result.reason_code == REASON_OK
    assert result.remaining_budget == 750.0
    assert result.reserved_amount == 250.0

def test_reserve_budget_insufficient(test_agent_id):
    """Test reservation exceeding budget."""
    # First reserve most of it
    reserve_budget_atomic(test_agent_id, 900.0)
    
    # Try to reserve more than remaining
    result = reserve_budget_atomic(test_agent_id, 150.0)
    
    assert result.allowed is False
    assert result.reason_code == REASON_INSUFFICIENT
    assert result.remaining_budget == 100.0 # Should still be 100
    assert result.reserved_amount == 0.0

def test_invalid_amount(test_agent_id):
    """Test that negative amounts are rejected."""
    result = reserve_budget_atomic(test_agent_id, -50.0)
    assert result.allowed is False
    assert result.reason_code == REASON_INVALID_AMOUNT

def test_agent_not_found():
    """Test behavior when agent doesn't exist."""
    fake_id = uuid.uuid4()
    result = reserve_budget_atomic(fake_id, 100.0)
    assert result.allowed is False
    assert result.reason_code == REASON_AGENT_NOT_FOUND

def test_reset_spend(test_agent_id):
    """Test resetting the budget."""
    reserve_budget_atomic(test_agent_id, 500.0)
    assert get_remaining_budget(test_agent_id) == 500.0
    
    new_budget = reset_spend(test_agent_id)
    assert new_budget == 1000.0
    assert get_remaining_budget(test_agent_id) == 1000.0

def test_budget_rollback(test_agent_id):
    """Test rolling back a reservation."""
    reserve_budget_atomic(test_agent_id, 300.0)
    assert get_remaining_budget(test_agent_id) == 700.0
    
    # Rollback
    success = budget_rollback(test_agent_id, 300.0)
    assert success is True
    assert get_remaining_budget(test_agent_id) == 1000.0

def test_concurrent_reservations(test_agent_id):
    """Test 100+ concurrent reservations to ensure atomicity and exact limits."""
    # Cap is 1000.0. We will try 150 concurrent reservations of 10.0
    # Exactly 100 should succeed, 50 should fail.
    
    def make_reservation():
        return reserve_budget_atomic(test_agent_id, 10.0)
        
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(lambda _: make_reservation(), range(150)))
        
    successes = [r for r in results if r.allowed]
    failures = [r for r in results if not r.allowed]
    
    assert len(successes) == 100
    assert len(failures) == 50
    assert get_remaining_budget(test_agent_id) == 0.0
