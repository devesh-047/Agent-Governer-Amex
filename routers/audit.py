"""Audit APIs (Milestone 4).

Endpoints for retrieving the audit log feed, querying the log,
and verifying the hash-chain integrity.
"""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from db.base import SessionLocal
from db.models.audit_log import AuditLog
from schemas.audit import ChainIntegrityStatus
from services.hash_chain import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])

class AuditLogEntry(BaseModel):
    id: uuid.UUID
    timestamp: str
    agent_id: uuid.UUID
    action_type: str
    amount: float
    decision: str
    reason: Optional[str] = None
    reason_code: str
    policy_version: str
    hash: str

    class Config:
        from_attributes = True

@router.get("/feed", response_model=List[AuditLogEntry])
def get_audit_feed(limit: int = Query(50, ge=1, le=200)):
    """Get the most recent audit log entries for live feed."""
    with SessionLocal() as db:
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
        return [
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp.isoformat(),
                agent_id=log.agent_id,
                action_type=log.action_type,
                amount=float(log.amount),
                decision=log.decision,
                reason=log.reason,
                reason_code=log.reason_code,
                policy_version=log.policy_version,
                hash=log.hash
            ) for log in logs
        ]

@router.get("/log", response_model=List[AuditLogEntry])
def get_audit_log(
    agent_id: Optional[uuid.UUID] = None,
    action_type: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Query the audit log with optional filters."""
    with SessionLocal() as db:
        query = db.query(AuditLog)
        
        if agent_id:
            query = query.filter(AuditLog.agent_id == agent_id)
        if action_type:
            query = query.filter(AuditLog.action_type == action_type)
        if decision:
            query = query.filter(AuditLog.decision == decision)
            
        logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
        return [
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp.isoformat(),
                agent_id=log.agent_id,
                action_type=log.action_type,
                amount=float(log.amount),
                decision=log.decision,
                reason=log.reason,
                reason_code=log.reason_code,
                policy_version=log.policy_version,
                hash=log.hash
            ) for log in logs
        ]

@router.post("/verify-chain", response_model=ChainIntegrityStatus)
def trigger_verify_chain():
    """Trigger a full hash-chain verification."""
    try:
        return verify_chain()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chain verification failed to execute: {e}")

@router.get("/integrity", response_model=ChainIntegrityStatus)
def get_chain_integrity():
    """Get the current hash-chain integrity status."""
    try:
        return verify_chain()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chain verification failed to execute: {e}")
