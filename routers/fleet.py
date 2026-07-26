"""
Fleet Control Router (Milestone B - Task 3.2)

所有权: D2

This module implements fleet-wide halt and resume endpoints.

Operation order (fail-closed):
1. Check current fleet state
2. Update Redis state (fleet:halted)
3. Write audit log via record_decision()
4. Return response

Consistency model:
- If Redis fails: 503, no audit written
- If Redis succeeds but audit fails: 503, state changed, audit incomplete
  (operator manual reconciliation required)

Redis keys (D2-owned):
- fleet:halted - "true" or "false"
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from schemas.audit import DecisionEvent, AuditWriteResult, HashChainError
from services.hash_chain import record_decision
from services.runtime_state import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fleet", tags=["fleet"])


# Sentinel UUID for fleet operations (system-level actions)
_SYSTEM_AGENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_redis():
    """Get the configured Redis client."""
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis client not configured")
    return client


def _get_fleet_state() -> str | None:
    """Get current fleet state from Redis.

    Returns:
        "true", "false", or None if key doesn't exist
    """
    redis_client = _get_redis()
    value = redis_client.get("fleet:halted")

    if value is None:
        return None

    # Handle both bytes and str
    if isinstance(value, bytes):
        value = value.decode('utf-8')

    # Canonical values are "true" and "false"
    if value in ("true", "false"):
        return value

    # Malformed value - treat as missing (fail-closed)
    logger.warning(f"Malformed fleet:halted value: {value!r}")
    return None


def _audit_fleet_action(
    action_type: str,
    reason_code: str,
    previous_halted: bool,
) -> uuid.UUID | None:
    """Write audit log entry for fleet state change.

    Args:
        action_type: Type of action (e.g., "FLEET_HALT")
        reason_code: Machine-readable reason code
        previous_halted: Previous fleet state

    Returns:
        audit_log_id if successful, None otherwise
    """
    try:
        event = DecisionEvent(
            agent_id=_SYSTEM_AGENT_ID,
            action_type=action_type,
            amount=0.0,  # Fleet control actions have no financial amount
            decision="allow",
            policy_version="runtime-control",
            reason=f"Fleet state changed from halted={previous_halted}",
            reason_code=reason_code,
            timestamp=datetime.now(timezone.utc),
        )

        result: AuditWriteResult = record_decision(event)
        return result.audit_log_id

    except HashChainError as e:
        logger.error(f"Failed to write audit log: {e}")
        return None


@router.post("/halt", response_model=dict)
def halt_fleet() -> dict:
    """Halt the entire fleet, preventing all agent requests.

    Operation order:
    1. Check current fleet state
    2. Set Redis key fleet:halted = "true"
    3. Write audit log
    4. Return 200 with audit_log_id

    Returns:
        Response with previous_halted, new_halted, audit_log_id

    Raises:
        HTTPException 503: Redis or database unavailable
    """
    # Get current state for audit
    current_value = _get_fleet_state() or "false"
    previous_halted = current_value == "true"

    # If already halted, return success (idempotent)
    if previous_halted:
        # Still write audit log for the attempt
        audit_log_id = _audit_fleet_action(
            action_type="FLEET_HALT",
            reason_code="OK",
            previous_halted=True,
        )
        return {
            "previous_halted": True,
            "new_halted": True,
            "audit_log_id": str(audit_log_id) if audit_log_id else None,
        }

    # Update Redis state
    try:
        redis_client = _get_redis()
        redis_client.set("fleet:halted", "true")
    except Exception as e:
        logger.error(f"Redis SET failed for fleet:halted: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime state unavailable"
        )

    # Write audit log
    audit_log_id = _audit_fleet_action(
        action_type="FLEET_HALT",
        reason_code="OK",
        previous_halted=previous_halted,
    )

    # Check if audit write failed
    if audit_log_id is None:
        # Redis succeeded but audit failed - inconsistent state
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="State changed but audit write failed"
        )

    # Return response
    return {
        "previous_halted": previous_halted,
        "new_halted": True,
        "audit_log_id": str(audit_log_id),
    }


@router.post("/resume", response_model=dict)
def resume_fleet() -> dict:
    """Resume the halted fleet, allowing agent requests.

    Operation order:
    1. Check current fleet state
    2. Set Redis key fleet:halted = "false"
    3. Write audit log
    4. Return 200 with audit_log_id

    Returns:
        Response with previous_halted, new_halted, audit_log_id

    Raises:
        HTTPException 503: Redis or database unavailable
    """
    # Get current state for audit
    # Missing key defaults to "false" (overlay model: missing = operational)
    current_value = _get_fleet_state() or "false"
    previous_halted = current_value == "true"

    # If already active, return success (idempotent)
    if not previous_halted:
        # Still write audit log for the attempt
        audit_log_id = _audit_fleet_action(
            action_type="FLEET_RESUME",
            reason_code="OK",
            previous_halted=False,
        )
        # Check if audit write failed
        if audit_log_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Audit write failed"
            )
        return {
            "previous_halted": False,
            "new_halted": False,
            "audit_log_id": str(audit_log_id),
        }

    # Update Redis state
    try:
        redis_client = _get_redis()
        redis_client.set("fleet:halted", "false")
    except Exception as e:
        logger.error(f"Redis SET failed for fleet:halted: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime state unavailable"
        )

    # Write audit log
    audit_log_id = _audit_fleet_action(
        action_type="FLEET_RESUME",
        reason_code="OK",
        previous_halted=previous_halted,
    )

    # Check if audit write failed
    if audit_log_id is None:
        # Redis succeeded but audit failed - inconsistent state
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="State changed but audit write failed"
        )

    # Return response
    return {
        "previous_halted": previous_halted,
        "new_halted": False,
        "audit_log_id": str(audit_log_id),
    }

@router.get("/state")
def get_fleet_state() -> dict:
    """Get the current fleet halt status."""
    try:
        current_value = _get_fleet_state()
        is_halted = current_value == "true"
        return {
            "fleet_halted": is_halted,
            "available": True
        }
    except Exception as e:
        logger.error(f"Failed to get fleet state from Redis: {e}")
        # Fail closed on read
        return {
            "fleet_halted": True,
            "available": False
        }


# Export for main.py to register
__all__ = ["router"]
