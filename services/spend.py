"""Spend-cap enforcement service (Milestone 1 / Task 2.4).

Ownership: services/spend.py

Atomic budget reservation using Redis integer counters (cents).

Key design decisions:
- Amounts stored as INTEGER CENTS in Redis (no floats) for exact atomicity via DECRBY.
- SETNX-based initialisation: first request for an agent initialises the counter
  from the DB daily_cap if the Redis key is absent, race-safe.
- Fail-closed: any Redis exception → SpendResult(allowed=False, reason_code="REDIS_UNAVAILABLE").
- budget_rollback(): caller (orchestrator) can refund a successful reservation when
  a subsequent step (e.g. audit write) fails.

Redis key domain:
  agent:{agent_id}:remaining_budget   ← owned exclusively by this module
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from db.base import SessionLocal
from db.models.agent import Agent
from services.runtime_state import get_redis_client

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Public result type
# ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SpendResult:
    """Result of a spend-cap evaluation or reservation.

    Fields
    ------
    allowed : bool
        True when the reservation was accepted.
    remaining_budget : float
        Remaining daily budget AFTER this operation (in dollars).
    reserved_amount : float
        Amount that was actually reserved (0.0 on deny).
    reason_code : str
        Machine-readable outcome code (see REASON_* constants below).
    reason : str
        Human-readable explanation.
    """
    allowed: bool
    remaining_budget: float
    reserved_amount: float
    reason_code: str
    reason: str = ""


# ────────────────────────────────────────────────────────────
# Reason codes
# ────────────────────────────────────────────────────────────

REASON_OK = "OK"
REASON_INSUFFICIENT = "SPEND_CAP_EXCEEDED"
REASON_REDIS_UNAVAILABLE = "RUNTIME_STATE_UNAVAILABLE"
REASON_AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
REASON_INVALID_AMOUNT = "INVALID_AMOUNT"


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _redis_key(agent_id: uuid.UUID) -> str:
    return f"agent:{agent_id}:remaining_budget"


def _to_cents(amount: float) -> int:
    """Convert a dollar amount to integer cents, rounding half-up."""
    return int(Decimal(f"{amount:.4f}").quantize(Decimal("0.01")) * 100)


def _from_cents(cents: int) -> float:
    """Convert integer cents back to dollars."""
    return cents / 100.0


def _parse_redis_int(raw: bytes | str | None) -> Optional[int]:
    """Decode a raw Redis value as int, or None if not present/invalid."""
    if raw is None:
        return None
    try:
        if isinstance(raw, (bytes, bytearray)):
            return int(raw)
        return int(raw)
    except (ValueError, TypeError):
        return None


def _get_daily_cap_cents(agent_id: uuid.UUID) -> Optional[int]:
    """Fetch the agent's daily_cap from Postgres and return it in cents.

    Returns None if the agent does not exist.
    """
    with SessionLocal() as db:
        agent: Optional[Agent] = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent is None:
            return None
        return _to_cents(float(agent.daily_cap))


def _ensure_budget_initialised(agent_id: uuid.UUID, redis_client) -> Optional[int]:
    """Ensure the Redis budget key exists, initialising from DB if absent.

    Returns the current budget in cents, or None if the agent is not found.

    Race-safety: uses SET NX so that concurrent first-requests collapse to a
    single initialisation; the winner's value is the authoritative starting point.
    """
    key = _redis_key(agent_id)
    raw = redis_client.get(key)
    existing = _parse_redis_int(raw)
    if existing is not None:
        return existing

    # Key absent → initialise from DB
    cap_cents = _get_daily_cap_cents(agent_id)
    if cap_cents is None:
        return None

    # SET NX: only write if the key still doesn't exist (another thread may have
    # just written it between our GET and this SET).
    redis_client.set(key, str(cap_cents), nx=True)

    # Read back whatever is now canonical (our value or the concurrent winner's)
    raw_after = redis_client.get(key)
    return _parse_redis_int(raw_after) or cap_cents


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def get_remaining_budget(agent_id: uuid.UUID) -> float:
    """Return the agent's current remaining budget in dollars.

    Initialises the Redis key from DB if absent.

    Raises
    ------
    RuntimeError
        If the Redis client has not been wired.
    RuntimeError
        If Redis is unreachable.
    ValueError
        If the agent does not exist.
    """
    redis_client = get_redis_client()
    if redis_client is None:
        raise RuntimeError("Redis client not configured")

    key = _redis_key(agent_id)
    raw = redis_client.get(key)
    cents = _parse_redis_int(raw)
    if cents is not None:
        return _from_cents(cents)

    # Not initialised yet
    cap_cents = _get_daily_cap_cents(agent_id)
    if cap_cents is None:
        raise ValueError(f"Agent {agent_id} not found")

    redis_client.set(key, str(cap_cents), nx=True)
    raw2 = redis_client.get(key)
    return _from_cents(_parse_redis_int(raw2) or cap_cents)


def reserve_budget_atomic(agent_id: uuid.UUID, amount: float) -> SpendResult:
    """Atomically reserve *amount* dollars from the agent's daily budget.

    Algorithm
    ---------
    1. Validate amount.
    2. Ensure the Redis counter is initialised (SETNX from DB on first use).
    3. DECRBY the counter by amount_cents.
    4. If new value < 0:  INCRBY to restore (compensating increment) → deny.
    5. If new value >= 0: allow, return remaining budget.

    Fail-closed: any Redis exception → deny with RUNTIME_STATE_UNAVAILABLE.

    Parameters
    ----------
    agent_id : uuid.UUID
    amount   : float  (dollar amount, two decimal precision expected)

    Returns
    -------
    SpendResult
    """
    if amount < 0:
        return SpendResult(
            allowed=False,
            remaining_budget=0.0,
            reserved_amount=0.0,
            reason_code=REASON_INVALID_AMOUNT,
            reason="Amount must be non-negative",
        )

    amount_cents = _to_cents(amount)
    key = _redis_key(agent_id)

    try:
        redis_client = get_redis_client()
        if redis_client is None:
            return SpendResult(
                allowed=False,
                remaining_budget=0.0,
                reserved_amount=0.0,
                reason_code=REASON_REDIS_UNAVAILABLE,
                reason="Redis client not configured",
            )

        # Step 1: Ensure counter exists
        current_cents = _ensure_budget_initialised(agent_id, redis_client)
        if current_cents is None:
            return SpendResult(
                allowed=False,
                remaining_budget=0.0,
                reserved_amount=0.0,
                reason_code=REASON_AGENT_NOT_FOUND,
                reason=f"Agent {agent_id} not found in database",
            )

        # Step 2: Atomic decrement
        new_cents: int = redis_client.decrby(key, amount_cents)

        # Step 3: Check for overspend
        if new_cents < 0:
            # Compensating increment – restore the balance
            redis_client.incrby(key, amount_cents)
            # Read back the authoritative remaining balance
            raw = redis_client.get(key)
            remaining_cents = _parse_redis_int(raw) or 0
            return SpendResult(
                allowed=False,
                remaining_budget=_from_cents(max(remaining_cents, 0)),
                reserved_amount=0.0,
                reason_code=REASON_INSUFFICIENT,
                reason=(
                    f"Requested {amount:.2f} exceeds remaining daily budget "
                    f"of {_from_cents(current_cents):.2f}"
                ),
            )

        # Step 4: Allow
        return SpendResult(
            allowed=True,
            remaining_budget=_from_cents(new_cents),
            reserved_amount=amount,
            reason_code=REASON_OK,
            reason="",
        )

    except Exception as exc:
        logger.error("Redis error during budget reservation for %s: %s", agent_id, exc)
        return SpendResult(
            allowed=False,
            remaining_budget=0.0,
            reserved_amount=0.0,
            reason_code=REASON_REDIS_UNAVAILABLE,
            reason=f"Redis unavailable: {exc}",
        )


def budget_rollback(agent_id: uuid.UUID, amount: float) -> bool:
    """Refund a previously reserved amount back to the agent's budget.

    Called by the orchestrator when an audit write fails after a successful
    spend reservation (to maintain the spend→audit atomicity guarantee).

    Returns True on success, False on failure (logs the error; caller must
    decide whether to raise HTTP 503).
    """
    if amount <= 0:
        return True

    amount_cents = _to_cents(amount)
    key = _redis_key(agent_id)

    try:
        redis_client = get_redis_client()
        if redis_client is None:
            logger.error("Cannot rollback budget for %s: Redis not configured", agent_id)
            return False

        redis_client.incrby(key, amount_cents)
        logger.info("Budget rollback applied for %s: %.2f refunded", agent_id, amount)
        return True

    except Exception as exc:
        logger.error("Budget rollback failed for %s (%.2f): %s", agent_id, amount, exc)
        return False


def reset_spend(agent_id: uuid.UUID) -> float:
    """Reset an agent's remaining budget to their current daily_cap.

    Reads the cap from Postgres and writes it directly to Redis.

    Returns
    -------
    float
        The new remaining budget (= daily_cap).

    Raises
    ------
    ValueError
        If the agent does not exist.
    RuntimeError
        If the Redis client is not configured or unreachable.
    """
    redis_client = get_redis_client()
    if redis_client is None:
        raise RuntimeError("Redis client not configured")

    cap_cents = _get_daily_cap_cents(agent_id)
    if cap_cents is None:
        raise ValueError(f"Agent {agent_id} not found")

    key = _redis_key(agent_id)
    redis_client.set(key, str(cap_cents))
    logger.info("Spend reset for agent %s: budget restored to %.2f", agent_id, _from_cents(cap_cents))
    return _from_cents(cap_cents)
