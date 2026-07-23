from db.base import SessionLocal
from db.models.agent import Agent
from services.identity import AgentLookup

class D1AgentLookup(AgentLookup):
    def get_agent_secret(self, agent_id: str) -> str | None:
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter_by(id=agent_id).first()
            return agent.shared_secret if agent else None
        finally:
            db.close()