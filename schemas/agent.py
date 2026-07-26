"""Pydantic schemas for agent management endpoints (Milestones 3 & 4)."""

from __future__ import annotations

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class PolicyUpdateRequest(BaseModel):
    """Body of PUT /agents/{id}/policy."""
    permissions: List[str] = Field(..., description="Allowed action types")
    max_single_amount: float = Field(..., ge=0.0, description="Max single-transaction amount")
    daily_cap: float = Field(..., ge=0.0, description="Daily spending cap")


class AgentResponse(BaseModel):
    """Serialised view of an Agent row (no secrets)."""
    id: str
    name: str
    permissions: List[str]
    max_single_amount: float
    daily_cap: float
    status: str                        # active | revoked (persisted)
    runtime_status: Optional[str] = None   # live from Redis if available
    fleet_halted: Optional[bool] = None    # live from Redis if available
    remaining_budget: Optional[float] = None  # live from Redis if available

    class Config:
        from_attributes = True
