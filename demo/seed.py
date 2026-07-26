import uuid
import logging
from sqlalchemy import text
from db.base import SessionLocal
from db.models.agent import Agent
from db.models.audit_log import AuditLog
from services.redis_client import create_redis_client_from_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Deterministic UUIDs for demo agents
SYSTEM_AGENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
AGENT_A_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
AGENT_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
AGENT_C_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

DEMO_AGENTS = [
    Agent(
        id=SYSTEM_AGENT_ID,
        name="System Agent",
        permissions=["system"],
        max_single_amount=0.00,
        daily_cap=0.00,
        status="active",
        shared_secret="system-secret",
    ),
    Agent(
        id=AGENT_A_ID,
        name="Payments Automation (Compliant)",
        permissions=["refund"],
        max_single_amount=500.00,
        daily_cap=2000.00,
        status="active",
        shared_secret="secret-compliant-A",
    ),
    Agent(
        id=AGENT_B_ID,
        name="Travel Booking Agent (Policy Violator)",
        permissions=["travel_booking"],
        max_single_amount=100.00,
        daily_cap=500.00,
        status="active",
        shared_secret="secret-violator-B",
    ),
    Agent(
        id=AGENT_C_ID,
        name="Rewards Adjustment Agent (Runaway)",
        permissions=["points_adjustment"],
        max_single_amount=1000.00,
        daily_cap=10000.00,
        status="active",
        shared_secret="secret-runaway-C",
    ),
]

def seed_demo_environment():
    logger.info("Starting demo environment seed...")
    db = SessionLocal()
    redis_client = create_redis_client_from_env()

    try:
        # 1. Clear ALL existing data (to remove old test agents and ensure a clean dashboard)
        logger.info("Cleaning up old audit logs...")
        db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER ALL"))
        db.query(AuditLog).delete(synchronize_session=False)
        db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER ALL"))
        
        logger.info("Cleaning up old agents...")
        db.query(Agent).delete(synchronize_session=False)
        db.commit()

        # 2. Insert new demo agents
        logger.info("Inserting demo agents...")
        for agent in DEMO_AGENTS:
            db.add(agent)
        db.commit()

        # 3. Reset Redis state for these agents
        logger.info("Resetting Redis state for demo agents...")
        # Un-halt fleet
        redis_client.set("fleet:halted", "false")

        for agent in DEMO_AGENTS:
            # Set active status
            redis_client.set(f"agent:{agent.id}:status", "active")
            # Set budget in cents!
            budget_cents = int(float(agent.daily_cap) * 100)
            redis_client.set(f"agent:{agent.id}:remaining_budget", str(budget_cents))
            
        logger.info("Demo environment seeded successfully.")

    except Exception as e:
        logger.error(f"Error seeding demo environment: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_environment()
