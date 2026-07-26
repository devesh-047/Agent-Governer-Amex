"""Frozen contract types for the audit system (Task 2.2).

所有权: D2

These types define the canonical contract between the policy system (D1)
and the audit system (D2) for recording decisions with hash-chain integrity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class DecisionEvent:
    """Canonical event record for an action decision.

    This type is frozen - changes require explicit review.

    Fields are in alphabetical order for canonicalization:
    - action_type: str - The type of action being requested
    - agent_id: UUID - The agent making the request
    - amount: float - Amount in financial units (2 decimal precision)
    - decision: "allow" | "deny" - Final decision
    - policy_version: str - Version of the policy that made the decision
    - reason: str | None - Human-readable explanation (nullable)
    - reason_code: str - Machine-readable reason code
    - timestamp: datetime - When the decision was made (must be timezone-aware)

    The amount field is float (not Decimal) because this is the public contract.
    The hash_chain service canonicalizes it to 2-decimal string for hashing.
    """

    action_type: str
    agent_id: uuid.UUID
    amount: float
    decision: Literal["allow", "deny"]
    policy_version: str
    reason: str | None
    reason_code: str
    timestamp: datetime


@dataclass(frozen=True)
class AuditWriteResult:
    """Result of successfully writing a decision to the audit log.

    This type is frozen - changes require explicit review.

    Fields:
    - audit_log_id: UUID - The ID of the created audit_log row
    - hash: str - The SHA-256 hash of the row (including prev_hash linkage)
    """

    audit_log_id: uuid.UUID
    hash: str


class HashChainError(Exception):
    """Raised when a hash-chain operation fails.

    This exception indicates a problem with the audit write process,
    such as database connection failure or violation of hash-chain integrity.
    """


@dataclass(frozen=True)
class ChainIntegrityStatus:
    """Result of hash-chain verification.

    This type is frozen - changes require explicit review.
    """
    intact: bool                          # True if entire chain verified
    verified_count: int                   # Number of rows verified
    broken_at_row: int | None = None      # 1-indexed row where chain breaks
    first_broken_id: uuid.UUID | None = None  # ID of first broken row
    error_type: Literal[None, "HASH_MISMATCH"] = None
    message: str = ""                     # Human-readable summary
