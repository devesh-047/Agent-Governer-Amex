import httpx
import logging

logger = logging.getLogger(__name__)

class DemoAgent:
    def __init__(self, name: str, agent_id: str, secret: str, base_url: str = "http://localhost:8000"):
        self.name = name
        self.agent_id = str(agent_id)
        self.secret = secret
        self.base_url = base_url
        self.client = httpx.Client(base_url=self.base_url, headers={
            "X-Agent-Id": self.agent_id,
            "X-Agent-Secret": self.secret
        })

    def request_action(self, action_type: str, amount: float) -> httpx.Response:
        """Issue a request to the governance gateway."""
        return self.client.post("/action-request", json={
            "action_type": action_type,
            "amount": amount,
            "metadata": {"source": "demo_runner"}
        })
