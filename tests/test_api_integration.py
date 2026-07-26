"""Integration tests for Policy, Audit, and Action APIs (Milestones 3, 4, 5)."""

import uuid
import pytest
from fastapi.testclient import TestClient

from main import app, bootstrap_dependencies
from db.base import SessionLocal
from db.models.agent import Agent
from services.runtime_state import get_redis_client

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_redis_for_tests():
    """Ensure redis is configured before every test."""
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
def test_agent():
    """Create a temporary agent in the DB for API testing."""
    agent_id = uuid.uuid4()
    secret = "test_secret"
    
    with SessionLocal() as db:
        agent = Agent(
            id=agent_id,
            name="API Test Agent",
            permissions=["refund"],
            max_single_amount=200.0,
            daily_cap=1000.0,
            status="active",
            shared_secret=secret
        )
        db.add(agent)
        db.commit()
    
    yield {"id": str(agent_id), "secret": secret}
    
    # We do NOT delete the agent from the DB during teardown, because if an audit log
    # was written for this agent, the foreign key constraint will block the delete,
    # and the audit_log table has append-only triggers preventing its deletion.
        
    redis_client = get_redis_client()
    if redis_client:
        redis_client.client.delete(f"agent:{agent_id}:remaining_budget")
        redis_client.client.delete(f"agent:{agent_id}:status")
        redis_client.client.delete("fleet:halted")

def test_policy_update(test_agent):
    """Test PUT /agents/{id}/policy."""
    agent_id = test_agent["id"]
    payload = {
        "permissions": ["refund", "credit"],
        "max_single_amount": 500.0,
        "daily_cap": 2000.0
    }
    
    response = client.put(f"/agents/{agent_id}/policy", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["permissions"] == ["refund", "credit"]
    assert data["max_single_amount"] == 500.0
    assert data["daily_cap"] == 2000.0

def test_reset_spend(test_agent):
    """Test POST /agents/{id}/reset-spend."""
    agent_id = test_agent["id"]
    response = client.post(f"/agents/{agent_id}/reset-spend")
    assert response.status_code == 200
    assert response.json()["new_remaining_budget"] == 1000.0

def test_action_request_success(test_agent):
    """Test successful action orchestration."""
    agent_id = test_agent["id"]
    secret = test_agent["secret"]
    
    headers = {
        "X-Agent-Id": agent_id,
        "X-Agent-Secret": secret
    }
    payload = {
        "action_type": "refund",
        "amount": 100.0
    }
    
    response = client.post("/action-request", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "allow"
    assert data["reason_code"] == "OK"
    assert data["remaining_budget"] == 900.0
    assert "audit_log_id" in data

def test_action_request_identity_failure(test_agent):
    """Test action orchestration with invalid identity."""
    agent_id = test_agent["id"]
    
    headers = {
        "X-Agent-Id": agent_id,
        "X-Agent-Secret": "wrong_secret"
    }
    payload = {
        "action_type": "refund",
        "amount": 100.0
    }
    
    response = client.post("/action-request", headers=headers, json=payload)
    assert response.status_code == 401

def test_action_request_policy_deny(test_agent):
    """Test action orchestration failing policy evaluation."""
    agent_id = test_agent["id"]
    secret = test_agent["secret"]
    
    headers = {
        "X-Agent-Id": agent_id,
        "X-Agent-Secret": secret
    }
    payload = {
        "action_type": "invalid_action", # Not in permissions
        "amount": 100.0
    }
    
    response = client.post("/action-request", headers=headers, json=payload)
    assert response.status_code == 200 # Policy denies return 200 OK with decision=deny
    data = response.json()
    assert data["decision"] == "deny"
    assert data["reason_code"] == "PERMISSION_DENIED"

def test_action_request_spend_deny(test_agent):
    """Test action orchestration failing spend limit."""
    agent_id = test_agent["id"]
    secret = test_agent["secret"]
    
    headers = {
        "X-Agent-Id": agent_id,
        "X-Agent-Secret": secret
    }
    
    # Exceeds max_single_amount
    payload1 = {
        "action_type": "refund",
        "amount": 500.0 
    }
    response1 = client.post("/action-request", headers=headers, json=payload1)
    assert response1.status_code == 200
    assert response1.json()["decision"] == "deny"
    assert response1.json()["reason_code"] == "AMOUNT_EXCEEDS_LIMIT"

    # Exceeds daily cap
    payload2 = {
        "action_type": "refund",
        "amount": 200.0 
    }
    # Reserve total 1000.0 (5 * 200)
    for _ in range(5):
        client.post("/action-request", headers=headers, json=payload2)
        
    # Try one more, should fail spend cap
    response2 = client.post("/action-request", headers=headers, json=payload2)
    assert response2.status_code == 200
    assert response2.json()["decision"] == "deny"
    assert response2.json()["reason_code"] == "SPEND_CAP_EXCEEDED"

def test_audit_apis():
    """Test Audit log and feed APIs."""
    feed_response = client.get("/audit/feed")
    assert feed_response.status_code == 200
    feed_data = feed_response.json()
    assert isinstance(feed_data, list)
    
    log_response = client.get("/audit/log")
    assert log_response.status_code == 200
    log_data = log_response.json()
    assert isinstance(log_data, list)

def test_audit_verify_chain():
    """Test hash-chain verification endpoint."""
    response = client.post("/audit/verify-chain")
    assert response.status_code == 200
    data = response.json()
    assert data["intact"] is True
