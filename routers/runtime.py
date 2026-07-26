"""
Runtime Control Router (Milestone B - Task 3.1)

所有权: D2

This module implements agent revocation and restoration endpoints.

Operation order (fail-closed):
1. Validate agent exists in database
2. Update Redis state (agent:{id}:status)
3. Write audit log via record_decision()
4. Return response

Consistency model:
- If agent not found: 404, no state change
- If Redis fails: 503, no audit written
- If Redis succeeds but audit fails: 503, state changed, audit incomplete
  (operator manual reconciliation required)

Redis keys (D2-owned):
- agent:{id}:status - "active" or "revoked"
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.base import SessionLocal, engine
from schemas.audit import DecisionEvent, AuditWriteResult, HashChainError
from services.hash_chain import record_decision
from services.runtime_state import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["runtime"])


# Sentinel UUID for system operations (when no specific agent acts)
_SYSTEM_AGENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_redis():
    """Get the configured Redis client."""
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis client not configured")
    return client


def _agent_exists(agent_id: uuid.UUID) -> bool:
    """Check if agent exists in database.

    Args:
        agent_id: UUID of the agent to check

    Returns:
        True if agent exists, False otherwise
    """
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT id FROM agents WHERE id = :agent_id"),
            {"agent_id": agent_id}
        )
        return result.fetchone() is not None


def _get_current_status(agent_id: uuid.UUID) -> str | None:
    """Get current agent status from Redis.

    Args:
        agent_id: UUID of the agent

    Returns:
        "active", "revoked", or None if key doesn't exist
    """
    redis_client = _get_redis()
    key = f"agent:{agent_id}:status"
    value = redis_client.get(key)

    if value is None:
        return None

    # Handle both bytes and str
    if isinstance(value, bytes):
        value = value.decode('utf-8')

    # Canonical values are "active" and "revoked"
    if value in ("active", "revoked"):
        return value

    # Malformed value - treat as missing (fail-closed)
    logger.warning(f"Malformed status value for {key}: {value!r}")
    return None


def _audit_runtime_action(
    agent_id: uuid.UUID,
    action_type: str,
    reason_code: str,
    previous_status: str,
) -> uuid.UUID | None:
    """Write audit log entry for runtime state change.

    Args:
        agent_id: UUID of the agent
        action_type: Type of action (e.g., "AGENT_REVOKE")
        reason_code: Machine-readable reason code
        previous_status: Previous status before change

    Returns:
        audit_log_id if successful, None otherwise
    """
    try:
        event = DecisionEvent(
            agent_id=agent_id,
            action_type=action_type,
            amount=0.0,  # Runtime control actions have no financial amount
            decision="allow",
            policy_version="runtime-control",
            reason=f"Runtime state changed from {previous_status}",
            reason_code=reason_code,
            timestamp=datetime.now(timezone.utc),
        )

        result: AuditWriteResult = record_decision(event)
        return result.audit_log_id

    except HashChainError as e:
        logger.error(f"Failed to write audit log: {e}")
        return None


@router.post("/{agent_id}/revoke", response_model=dict)
def revoke_agent(agent_id: uuid.UUID) -> dict:
    """Revoke an agent, preventing it from making requests.

    Operation order:
    1. Validate agent exists (404 if not)
    2. Set Redis key agent:{id}:status = "revoked"
    3. Write audit log
    4. Return 200 with audit_log_id

    Args:
        agent_id: UUID of the agent to revoke

    Returns:
        Response with agent_id, previous_status, new_status, audit_log_id

    Raises:
        HTTPException 404: Agent not found
        HTTPException 503: Redis or database unavailable
    """
    # Step 1: Validate agent exists
    if not _agent_exists(agent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )

    # Get current status for audit
    previous_status = _get_current_status(agent_id) or "active"

    # If already revoked, return success (idempotent)
    if previous_status == "revoked":
        # Still write audit log for the attempt
        audit_log_id = _audit_runtime_action(
            agent_id=agent_id,
            action_type="AGENT_REVOKE",
            reason_code="OK",
            previous_status="revoked",
        )
        # Check if audit write failed
        if audit_log_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Audit write failed"
            )
        return {
            "agent_id": str(agent_id),
            "previous_status": "revoked",
            "new_status": "revoked",
            "audit_log_id": str(audit_log_id),
        }

    # Step 2: Update Redis state
    try:
        redis_client = _get_redis()
        key = f"agent:{agent_id}:status"
        redis_client.set(key, "revoked")
    except Exception as e:
        logger.error(f"Redis SET failed for {key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime state unavailable"
        )

    # Step 3: Write audit log
    audit_log_id = _audit_runtime_action(
        agent_id=agent_id,
        action_type="AGENT_REVOKE",
        reason_code="OK",
        previous_status=previous_status,
    )

    # Step 4: Check if audit write failed
    if audit_log_id is None:
        # Redis succeeded but audit failed - inconsistent state
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="State changed but audit write failed"
        )

    # Step 5: Return response
    return {
        "agent_id": str(agent_id),
        "previous_status": previous_status,
        "new_status": "revoked",
        "audit_log_id": str(audit_log_id),
    }


@router.post("/{agent_id}/restore", response_model=dict)
def restore_agent(agent_id: uuid.UUID) -> dict:
    """Restore a revoked agent to active status.

    Operation order:
    1. Validate agent exists (404 if not)
    2. Set Redis key agent:{id}:status = "active"
    3. Write audit log
    4. Return 200 with audit_log_id

    Args:
        agent_id: UUID of the agent to restore

    Returns:
        Response with agent_id, previous_status, new_status, audit_log_id

    Raises:
        HTTPException 404: Agent not found
        HTTPException 503: Redis or database unavailable
    """
    # Step 1: Validate agent exists
    if not _agent_exists(agent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )

    # Get current status for audit
    # Missing key defaults to "active" (overlay model: missing = operational)
    previous_status = _get_current_status(agent_id) or "active"

    # If already active, return success (idempotent)
    if previous_status == "active":
        # Still write audit log for the attempt
        audit_log_id = _audit_runtime_action(
            agent_id=agent_id,
            action_type="AGENT_RESTORE",
            reason_code="OK",
            previous_status="active",
        )
        # Check if audit write failed
        if audit_log_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Audit write failed"
            )
        return {
            "agent_id": str(agent_id),
            "previous_status": "active",
            "new_status": "active",
            "audit_log_id": str(audit_log_id),
        }

    # Step 2: Update Redis state
    try:
        redis_client = _get_redis()
        key = f"agent:{agent_id}:status"
        redis_client.set(key, "active")
    except Exception as e:
        logger.error(f"Redis SET failed for {key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime state unavailable"
        )

    # Step 3: Write audit log
    audit_log_id = _audit_runtime_action(
        agent_id=agent_id,
        action_type="AGENT_RESTORE",
        reason_code="OK",
        previous_status=previous_status,
    )

    # Step 4: Check if audit write failed
    if audit_log_id is None:
        # Redis succeeded but audit failed - inconsistent state
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="State changed but audit write failed"
        )

    # Step 5: Return response
    return {
        "agent_id": str(agent_id),
        "previous_status": previous_status,
        "new_status": "active",
        "audit_log_id": str(audit_log_id),
    }


from typing import List
from db.models.agent import Agent
from schemas.agent import AgentResponse
from services.spend import get_remaining_budget
from services.runtime_state import check_runtime_status

@router.get("", response_model=List[AgentResponse])
def list_agents():
    """List all agents with their composed runtime status and remaining budget."""
    with SessionLocal() as db:
        agents = db.query(Agent).all()
        responses = []
        for agent in agents:
            status = check_runtime_status(agent.id)
            try:
                rem_budget = get_remaining_budget(agent.id)
            except Exception:
                rem_budget = None
                
            responses.append(AgentResponse(
                id=str(agent.id),
                name=agent.name,
                permissions=agent.permissions,
                max_single_amount=float(agent.max_single_amount),
                daily_cap=float(agent.daily_cap),
                status=agent.status,
                runtime_status="revoked" if status.agent_revoked else "active",
                fleet_halted=status.fleet_halted,
                remaining_budget=rem_budget
            ))
        return responses

@router.get("/{agent_id}/runtime-status")
def get_runtime_status(agent_id: uuid.UUID):
    """Get the live runtime status of an agent."""
    if not _agent_exists(agent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    status_obj = check_runtime_status(agent_id)
    return {
        "agent_id": str(agent_id),
        "available": status_obj.available,
        "fleet_halted": status_obj.fleet_halted,
        "agent_revoked": status_obj.agent_revoked
    }

# Export for main.py to register
__all__ = ["router"]
