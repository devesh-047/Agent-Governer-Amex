from dotenv import load_dotenv
load_dotenv()

import uuid
from db.base import SessionLocal
from db.models.agent import Agent

db = SessionLocal()

test_agent = Agent(
    id=uuid.uuid4(),
    name="Agent A - Compliant",
    permissions=["refund", "card_replacement"],
    max_single_amount=1000.00,
    daily_cap=5000.00,
    status="active",
    shared_secret="test-secret-123",
)

db.add(test_agent)
db.commit()

print(f"Seeded agent: {test_agent.id}")
db.close()