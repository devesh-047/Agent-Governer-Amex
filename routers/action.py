"""Action Orchestration API (Milestone 5).

Main gateway endpoint for agent requests.
Executes the canonical evaluation pipeline:
1. Identity
2. Fleet status
3. Agent status
4. Policy evaluation
5. Spend reservation
6. Audit recording
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.orm import Session

from db.base import SessionLocal
from db.models.agent import Agent
from schemas.action import ActionRequest, ActionResponse
from schemas.audit import DecisionEvent, AuditWriteResult, HashChainError
from services.hash_chain import record_decision
from services.identity import verify_identity
from services.runtime_state import check_runtime_status
from policy.opa_client import evaluate_policy
from services.spend import reserve_budget_atomic, budget_rollback, get_remaining_budget

logger = logging.getLogger(__name__)

router = APIRouter(tags=["action"])

@router.post("/action-request", response_model=ActionResponse)
def handle_action_request(
    request: ActionRequest,
    x_agent_id: str = Header(..., alias="X-Agent-Id"),
    x_agent_secret: str = Header(..., alias="X-Agent-Secret"),
):
    """Orchestrate an agent action request through the governance pipeline."""
    # 1. Identity Verification
    identity_result = verify_identity(x_agent_id, x_agent_secret)
    if not identity_result.valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credentials"
        )
    
    agent_id = uuid.UUID(identity_result.agent_id)
    
    # Pre-fetch agent from DB for policy/spend
    with SessionLocal() as db:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Agent not found"
            )
        # Detach agent from session since we only need its data
        db.expunge(agent)

    def _deny_and_audit(reason_code: str, reason: str, policy_version: str, status_code: int, remaining_budget: float = 0.0):
        try:
            event = DecisionEvent(
                agent_id=agent_id,
                action_type=request.action_type,
                amount=request.amount,
                decision="deny",
                policy_version=policy_version,
                reason=reason,
                reason_code=reason_code,
                timestamp=datetime.now(timezone.utc),
            )
            audit_result = record_decision(event)
            detail = {
                "decision": "deny",
                "reason_code": reason_code,
                "reason": reason,
                "remaining_budget": remaining_budget,
                "audit_log_id": str(audit_result.audit_log_id),
                "hash": audit_result.hash
            }
            if status_code == 200:
                return detail
            raise HTTPException(status_code=status_code, detail=detail)
        except HashChainError as e:
            logger.error(f"Failed to audit deny decision: {e}")
            # If we can't even audit the deny, fail closed
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Audit system unavailable")
            
    # 2 & 3. Runtime Safety (Fleet & Agent)
    runtime_status = check_runtime_status(agent_id)
    if not runtime_status.available:
        return _deny_and_audit(
            reason_code="RUNTIME_STATE_UNAVAILABLE",
            reason="Runtime state Redis unavailable",
            policy_version="gateway-1.0",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
        
    if runtime_status.fleet_halted:
        return _deny_and_audit(
            reason_code="FLEET_HALTED",
            reason="Fleet is halted by operator",
            policy_version="gateway-1.0",
            status_code=status.HTTP_403_FORBIDDEN
        )
        
    if runtime_status.agent_revoked:
        return _deny_and_audit(
            reason_code="AGENT_REVOKED",
            reason="Agent is revoked by operator",
            policy_version="gateway-1.0",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 4. Policy Evaluation
    policy_result = evaluate_policy(
        permissions=agent.permissions,
        max_single_amount=float(agent.max_single_amount),
        action_type=request.action_type,
        amount=request.amount
    )
    
    if not policy_result.allowed:
        try:
            rem_budget = get_remaining_budget(agent_id)
        except Exception:
            rem_budget = 0.0
        return _deny_and_audit(
            reason_code=policy_result.reason_code,
            reason=policy_result.reason,
            policy_version=policy_result.policy_version,
            status_code=status.HTTP_200_OK,
            remaining_budget=rem_budget
        )

    # 5. Spend Reservation
    spend_result = reserve_budget_atomic(agent_id, request.amount)
    if spend_result.reason_code == "RUNTIME_STATE_UNAVAILABLE":
        return _deny_and_audit(
            reason_code="RUNTIME_STATE_UNAVAILABLE",
            reason="Spend state Redis unavailable",
            policy_version="gateway-1.0",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
        
    if not spend_result.allowed:
        return _deny_and_audit(
            reason_code=spend_result.reason_code,
            reason=spend_result.reason,
            policy_version="gateway-1.0",
            status_code=status.HTTP_200_OK,
            remaining_budget=spend_result.remaining_budget
        )

    # 6. Audit Recording (Allow)
    try:
        event = DecisionEvent(
            agent_id=agent_id,
            action_type=request.action_type,
            amount=request.amount,
            decision="allow",
            policy_version=policy_result.policy_version,
            reason=None,
            reason_code="OK",
            timestamp=datetime.now(timezone.utc),
        )
        audit_result = record_decision(event)
    except HashChainError as e:
        logger.error(f"Failed to audit allow decision: {e}")
        # Rollback budget since audit failed
        budget_rollback(agent_id, request.amount)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Audit system unavailable. Budget rollback applied."
        )

    # 7. Response
    return ActionResponse(
        decision="allow",
        reason_code="OK",
        remaining_budget=spend_result.remaining_budget,
        audit_log_id=str(audit_result.audit_log_id),
        hash=audit_result.hash
    )
