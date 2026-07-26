"""Policy management APIs (Milestone 3).

Endpoints for updating agent permissions and resetting spend limits.
These operations are audited.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from db.base import SessionLocal
from db.models.agent import Agent
from schemas.agent import PolicyUpdateRequest, AgentResponse
from schemas.audit import DecisionEvent, AuditWriteResult, HashChainError
from services.hash_chain import record_decision
from services.spend import reset_spend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["policy"])

def _audit_control_action(
    agent_id: uuid.UUID,
    action_type: str,
    reason: str,
) -> uuid.UUID | None:
    """Write an audit log entry for a control plane action."""
    try:
        event = DecisionEvent(
            agent_id=agent_id,
            action_type=action_type,
            amount=0.0,
            decision="allow",
            policy_version="control-plane",
            reason=reason,
            reason_code="OK",
            timestamp=datetime.now(timezone.utc),
        )
        result: AuditWriteResult = record_decision(event)
        return result.audit_log_id
    except HashChainError as e:
        logger.error(f"Failed to write audit log for control action: {e}")
        return None

@router.put("/{agent_id}/policy", response_model=AgentResponse)
def update_policy(agent_id: uuid.UUID, request: PolicyUpdateRequest):
    """Update an agent's policy permissions and limits."""
    with SessionLocal() as db:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        agent.permissions = request.permissions
        agent.max_single_amount = request.max_single_amount
        agent.daily_cap = request.daily_cap
        
        db.commit()
        db.refresh(agent)

        audit_log_id = _audit_control_action(
            agent_id=agent_id,
            action_type="POLICY_UPDATE",
            reason="Operator updated agent policy",
        )
        
        if not audit_log_id:
            logger.warning(f"Failed to audit policy update for agent {agent_id}")

        return AgentResponse(
            id=str(agent.id),
            name=agent.name,
            permissions=agent.permissions,
            max_single_amount=float(agent.max_single_amount),
            daily_cap=float(agent.daily_cap),
            status=agent.status
        )

@router.post("/{agent_id}/reset-spend")
def reset_agent_spend(agent_id: uuid.UUID):
    """Reset an agent's remaining budget to their daily cap."""
    try:
        new_budget = reset_spend(agent_id)
        
        audit_log_id = _audit_control_action(
            agent_id=agent_id,
            action_type="SPEND_RESET",
            reason="Operator reset agent spend limit",
        )
        
        if not audit_log_id:
            logger.warning(f"Failed to audit spend reset for agent {agent_id}")
            
        return {
            "agent_id": str(agent_id),
            "new_remaining_budget": new_budget,
            "audit_log_id": str(audit_log_id) if audit_log_id else None
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
