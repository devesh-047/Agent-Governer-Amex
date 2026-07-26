import pytest
from fastapi.testclient import TestClient
import uuid
import time
from main import app
from demo.seed import seed_demo_environment, AGENT_A_ID, AGENT_B_ID, AGENT_C_ID

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_demo_env():
    seed_demo_environment()

def test_demo_6_beat_scenario():
    # 1. Compliant Agent A
    response = client.post(
        "/action-request",
        json={"action_type": "refund", "amount": 100.0, "metadata": {}},
        headers={"X-Agent-Id": str(AGENT_A_ID), "X-Agent-Secret": "secret-compliant-A"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "allow"
    assert data["reason_code"] == "OK"

    # 2. Policy Violator Agent B (Over Cap)
    response = client.post(
        "/action-request",
        json={"action_type": "travel_booking", "amount": 1000.0, "metadata": {}},
        headers={"X-Agent-Id": str(AGENT_B_ID), "X-Agent-Secret": "secret-violator-B"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "deny"
    assert data["reason_code"] in ["AMOUNT_EXCEEDS_LIMIT", "SPEND_CAP_EXCEEDED", "PERMISSION_DENIED"]

    # 3. Revoke Agent B
    response = client.post(f"/agents/{AGENT_B_ID}/revoke")
    assert response.status_code == 200
    
    response = client.post(
        "/action-request",
        json={"action_type": "travel_booking", "amount": 50.0, "metadata": {}},
        headers={"X-Agent-Id": str(AGENT_B_ID), "X-Agent-Secret": "secret-violator-B"}
    )
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["decision"] == "deny"
    assert data["detail"]["reason_code"] == "AGENT_REVOKED"

    # 4. Runaway Agent C rapid fire
    for _ in range(3):
        response = client.post(
            "/action-request",
            json={"action_type": "points_adjustment", "amount": 50.0, "metadata": {}},
            headers={"X-Agent-Id": str(AGENT_C_ID), "X-Agent-Secret": "secret-runaway-C"}
        )
        assert response.status_code == 200
        assert response.json()["decision"] == "allow"

    # 5. Halt fleet
    response = client.post("/fleet/halt")
    assert response.status_code == 200

    response = client.post(
        "/action-request",
        json={"action_type": "points_adjustment", "amount": 50.0, "metadata": {}},
        headers={"X-Agent-Id": str(AGENT_C_ID), "X-Agent-Secret": "secret-runaway-C"}
    )
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["reason_code"] == "FLEET_HALTED"

    response = client.post(
        "/action-request",
        json={"action_type": "refund", "amount": 50.0, "metadata": {}},
        headers={"X-Agent-Id": str(AGENT_A_ID), "X-Agent-Secret": "secret-compliant-A"}
    )
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["reason_code"] == "FLEET_HALTED"

    # 6. Audit integrity
    response = client.post("/audit/verify-chain")
    assert response.status_code == 200
    data = response.json()
    assert data["intact"] == True
