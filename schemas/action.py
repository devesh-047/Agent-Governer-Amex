"""Pydantic schemas for action-request endpoint (Milestone 5).

These are the public HTTP request/response shapes.
Internal service types live in schemas/audit.py.
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    """Body of POST /action-request."""
    action_type: str = Field(..., description="Action type to perform (e.g. refund)")
    amount: float = Field(..., ge=0.0, description="Dollar amount (>= 0)")


class ActionResponse(BaseModel):
    """Response of POST /action-request for all completed decisions."""
    decision: str            # "allow" or "deny"
    reason_code: str
    reason: Optional[str] = None
    remaining_budget: float
    audit_log_id: str
    hash: str
