import time
import httpx
import logging
import sys

from demo.seed import seed_demo_environment, AGENT_A_ID, AGENT_B_ID, AGENT_C_ID
from demo.agents import DemoAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("runner")

BASE_URL = "http://localhost:8000"
DELAY_BETWEEN_BEATS = 2.0

def wait():
    time.sleep(DELAY_BETWEEN_BEATS)

def print_separator():
    print("\n" + "=" * 80)

def assert_state(condition: bool, message: str):
    if not condition:
        logger.error(f"VALIDATION FAILED: {message}")
        sys.exit(1)
    logger.info(f"VALIDATION PASSED: {message}")

def get_agent_status(agent_id: str):
    r = httpx.get(f"{BASE_URL}/agents/{agent_id}/runtime-status")
    r.raise_for_status()
    return r.json()

def get_fleet_status():
    r = httpx.get(f"{BASE_URL}/fleet/state")
    r.raise_for_status()
    return r.json()

def get_agent_info(agent_id: str):
    r = httpx.get(f"{BASE_URL}/agents")
    r.raise_for_status()
    for a in r.json():
        if a["id"] == str(agent_id):
            return a
    return None

def verify_audit_log(agent_id: str, expected_decision: str, expected_reason_code: str):
    r = httpx.get(f"{BASE_URL}/audit/log", params={"agent_id": agent_id, "limit": 1})
    r.raise_for_status()
    logs = r.json()
    assert_state(len(logs) > 0, f"Audit log exists for agent {agent_id}")
    latest = logs[0]
    assert_state(latest["decision"] == expected_decision, f"Audit decision is {expected_decision}")
    assert_state(latest["reason_code"] == expected_reason_code, f"Audit reason_code is {expected_reason_code}")
    return latest

def run_demo():
    print_separator()
    logger.info("INITIALIZING DEMO ENVIRONMENT")
    seed_demo_environment()
    print_separator()

    # Initialize Agents
    agent_a = DemoAgent("Payments Automation", AGENT_A_ID, "secret-compliant-A", BASE_URL)
    agent_b = DemoAgent("Travel Booking Agent", AGENT_B_ID, "secret-violator-B", BASE_URL)
    agent_c = DemoAgent("Rewards Adjustment Agent", AGENT_C_ID, "secret-runaway-C", BASE_URL)

    # BEAT 1
    logger.info("BEAT 1: Agent A (Compliant) issues normal in-policy refund")
    initial_budget = get_agent_info(AGENT_A_ID)["remaining_budget"]
    
    r = agent_a.request_action("refund", 100.0)
    assert_state(r.status_code == 200, f"Agent A received 200 OK (Got {r.status_code})")
    
    data = r.json()
    assert_state(data["decision"] == "allow", "Decision is allow")
    
    verify_audit_log(AGENT_A_ID, "allow", "OK")
    
    final_budget = get_agent_info(AGENT_A_ID)["remaining_budget"]
    assert_state(final_budget == initial_budget - 100.0, "Budget decremented correctly")
    wait()
    print_separator()

    # BEAT 2
    logger.info("BEAT 2: Agent B (Violator) attempts over-cap refund")
    r = agent_b.request_action("travel_booking", 1000.0) # Limit is 100
    assert_state(r.status_code == 200, f"Agent B received 200 OK (Got {r.status_code})")
    
    data = r.json()
    assert_state(data["decision"] == "deny", "Decision is deny")
    assert_state(data["reason_code"] == "AMOUNT_EXCEEDS_LIMIT" or data["reason_code"] == "SPEND_CAP_EXCEEDED", f"Reason code is correct ({data['reason_code']})")
    
    verify_audit_log(AGENT_B_ID, "deny", data["reason_code"])
    wait()
    print_separator()

    # BEAT 3
    logger.info("BEAT 3: Operator revokes Agent B")
    r = httpx.post(f"{BASE_URL}/agents/{AGENT_B_ID}/revoke")
    assert_state(r.status_code == 200, "Revoke endpoint returned 200")
    
    status = get_agent_status(AGENT_B_ID)
    assert_state(status["agent_revoked"] == True, "Agent B status is revoked")
    
    logger.info("Agent B attempts action after revocation")
    r = agent_b.request_action("travel_booking", 50.0)
    assert_state(r.status_code == 403, "Agent B received 403 Forbidden")
    
    data = r.json()["detail"]
    assert_state(data["decision"] == "deny", "Decision is deny")
    assert_state(data["reason_code"] == "AGENT_REVOKED", "Reason code is AGENT_REVOKED")
    
    verify_audit_log(AGENT_B_ID, "deny", "AGENT_REVOKED")
    wait()
    print_separator()

    # BEAT 4
    logger.info("BEAT 4: Agent C (Runaway) rapid-fires legitimate requests")
    for i in range(3):
        r = agent_c.request_action("points_adjustment", 50.0)
        assert_state(r.status_code == 200, "Agent C received 200 OK")
        data = r.json()
        assert_state(data["decision"] == "allow", "Decision is allow")
        time.sleep(0.2)
    verify_audit_log(AGENT_C_ID, "allow", "OK")
    wait()
    print_separator()

    # BEAT 5
    logger.info("BEAT 5: Operator hits fleet kill switch")
    r = httpx.post(f"{BASE_URL}/fleet/halt")
    assert_state(r.status_code == 200, "Halt endpoint returned 200")
    
    fleet_status = get_fleet_status()
    assert_state(fleet_status["fleet_halted"] == True, "Fleet is halted")
    
    logger.info("Agent C attempts action after fleet halt")
    r = agent_c.request_action("points_adjustment", 50.0)
    assert_state(r.status_code == 403, "Agent C received 403 Forbidden")
    data = r.json()["detail"]
    assert_state(data["reason_code"] == "FLEET_HALTED", "Reason code is FLEET_HALTED")
    
    logger.info("Agent A attempts action after fleet halt")
    r = agent_a.request_action("refund", 50.0)
    assert_state(r.status_code == 403, "Agent A received 403 Forbidden")
    data = r.json()["detail"]
    assert_state(data["reason_code"] == "FLEET_HALTED", "Reason code is FLEET_HALTED")
    
    wait()
    print_separator()

    # BEAT 6
    logger.info("BEAT 6: Audit log integrity check")
    r = httpx.post(f"{BASE_URL}/audit/verify-chain")
    assert_state(r.status_code == 200, "Verify-chain endpoint returned 200")
    
    data = r.json()
    assert_state(data["intact"] == True, "Hash chain is intact")
    
    print_separator()
    logger.info("DEMO RUNNER COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    try:
        run_demo()
    except httpx.ConnectError:
        logger.error("Failed to connect to backend. Is the server running at http://localhost:8000?")
        sys.exit(1)
